import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import (
    APIKeyOwnerType,
    APIKeyStatus,
    CallerType,
    PolicyEffect,
    ResourceStatus,
    ResourceType,
    SubjectType,
)
from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import (
    decode_access_token,
    generate_api_key_for_phone,
    generate_session_id,
    hash_api_key,
    hash_session_id,
    normalize_phone,
    verify_password,
)
from app.modules.auth.models import APIKey, AuthSession, PermissionPolicy
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    APIKeyCreateByPhone,
    AuthenticatedSubject,
    LoginRequest,
    PermissionPolicyCreate,
    SessionResponse,
    SessionStatusResponse,
    UserSummary,
)
from app.modules.org.models import OrgUnit, UserAccount
from app.modules.org.repository import OrgRepository


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AuthRepository(db)
        self.org_repository = OrgRepository(db)

    def issue_external_customer_api_key_by_phone(self, payload: APIKeyCreateByPhone) -> tuple[str, APIKey]:
        phone_normalized = normalize_phone(payload.phone)
        user = self.org_repository.get_active_external_user_by_phone(phone_normalized)
        if user is None:
            raise NotFoundError("active external customer not found by phone")

        generated = generate_api_key_for_phone(phone_normalized)
        api_key = APIKey(
            key_prefix=generated.key_prefix,
            key_hash=generated.key_hash,
            owner_type=APIKeyOwnerType.USER,
            owner_id=user.id,
            issued_for_phone=phone_normalized,
            name=payload.name,
            scopes=payload.scopes,
            status=APIKeyStatus.ACTIVE,
            expires_at=payload.expires_at,
        )
        self.repository.add_api_key(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        return generated.raw_key, api_key

    def authenticate_api_key(self, raw_key: str) -> AuthenticatedSubject:
        api_key = self.repository.get_api_key_by_hash(hash_api_key(raw_key))
        if api_key is None:
            raise UnauthorizedError("invalid api key")
        now = datetime.now(timezone.utc)
        if api_key.status != APIKeyStatus.ACTIVE:
            raise UnauthorizedError("api key is not active")
        if api_key.expires_at and api_key.expires_at <= now:
            raise UnauthorizedError("api key expired")

        user_id: str | None = None
        org_unit_id: str | None = None
        if api_key.owner_type == APIKeyOwnerType.USER:
            user = self.db.get(UserAccount, api_key.owner_id)
            if user is None or user.status != ResourceStatus.ACTIVE:
                raise UnauthorizedError("api key owner is not active")
            user_id = user.id
            org_unit_id = user.org_unit_id
        elif api_key.owner_type == APIKeyOwnerType.ORG_UNIT:
            org_unit_id = api_key.owner_id

        self.repository.mark_api_key_used(api_key, now)
        self.db.commit()
        return AuthenticatedSubject(
            caller_type=CallerType.API_KEY,
            user_id=user_id,
            org_unit_id=org_unit_id,
            api_key_id=api_key.id,
            scopes=api_key.scopes,
        )

    def create_permission_policy(self, payload: PermissionPolicyCreate) -> PermissionPolicy:
        policy = PermissionPolicy(
            subject_type=payload.subject_type,
            subject_id=payload.subject_id,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            actions=payload.actions,
            effect=payload.effect,
            status=ResourceStatus.ACTIVE,
        )
        self.repository.add_permission_policy(policy)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def assert_allowed(
        self,
        subject: AuthenticatedSubject,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> None:
        if subject.api_key_id and action not in subject.scopes and "*" not in subject.scopes:
            raise ForbiddenError("api key scope does not allow this action")

        subjects: list[tuple[str, str]] = []
        if subject.user_id:
            subjects.append((SubjectType.USER, subject.user_id))
        if subject.org_unit_id:
            subjects.append((SubjectType.ORG_UNIT, subject.org_unit_id))
        if subject.api_key_id:
            subjects.append((SubjectType.API_KEY, subject.api_key_id))

        policies = self._list_matching_policies(subjects, resource_type, resource_id)
        matching = [policy for policy in policies if action in policy.actions]
        if any(policy.effect == PolicyEffect.DENY for policy in matching):
            raise ForbiddenError("permission denied")
        if not any(policy.effect == PolicyEffect.ALLOW for policy in matching):
            raise ForbiddenError("permission denied")

    def _list_matching_policies(
        self,
        subjects: list[tuple[str, str]],
        resource_type: str,
        resource_id: str,
    ) -> list[PermissionPolicy]:
        return self.repository.list_active_policies_for_subjects(subjects, resource_type, resource_id)

    def list_api_keys(self) -> list[APIKey]:
        return self.repository.list_api_keys()

    def list_permission_policies(self) -> list[PermissionPolicy]:
        return self.repository.list_permission_policies()

    def get_user_summary(self, subject: AuthenticatedSubject) -> UserSummary:
        """根据认证主体获取用户摘要信息。"""
        if subject.user_id is None:
            raise UnauthorizedError("无法获取用户信息")
        user = self.org_repository.get_user(subject.user_id)
        if user is None:
            raise UnauthorizedError("用户不存在")
        org_unit = self.org_repository.get_org_unit(user.org_unit_id)
        return UserSummary(
            id=user.id,
            name=user.name,
            phone=user.phone_normalized,
            org_unit_id=user.org_unit_id,
            org_unit_name=org_unit.name if org_unit else None,
            is_admin=self._has_admin_permission(user),
        )

    def authenticate_bearer_token(self, raw_token: str) -> AuthenticatedSubject:
        """认证 Authorization Bearer 凭证。

        浏览器用户登录态已迁移到服务端 Session Cookie；Bearer 仅保留给外部系统
        和过渡期管理 API Key 使用。
        """
        return self.authenticate_api_key(raw_token)

    # ── 手机号密码登录 ──────────────────────────────────────────

    def login_by_phone_password(
        self,
        payload: LoginRequest,
        *,
        user_agent: str | None = None,
        client_ip: str | None = None,
    ) -> tuple[str, SessionResponse]:
        """手机号密码登录：规范化手机号，校验密码，创建服务端 session。

        登录失败统一返回 401，不区分"用户不存在"和"密码错误"，
        避免泄漏用户存在性。
        """
        phone_normalized = normalize_phone(payload.phone)
        user = self.org_repository.get_active_external_user_by_phone(phone_normalized)
        if user is None:
            raise UnauthorizedError("手机号或密码错误")
        if not user.password_hash:
            # 历史用户没有密码时统一返回认证失败
            raise UnauthorizedError("手机号或密码错误")
        if not verify_password(payload.password, user.password_hash):
            raise UnauthorizedError("手机号或密码错误")

        settings = get_settings()
        now = datetime.now(timezone.utc)
        raw_session_id = generate_session_id()
        session = AuthSession(
            session_hash=hash_session_id(raw_session_id),
            user_id=user.id,
            phone_normalized=user.phone_normalized,
            token_version=user.token_version,
            access_expires_at=now + timedelta(minutes=settings.access_token_expire_minutes),
            idle_expires_at=now + timedelta(minutes=settings.session_idle_expire_minutes),
            last_seen_at=now,
            user_agent_hash=self._hash_optional(user_agent),
            client_ip_hash=self._hash_optional(client_ip),
        )
        self.repository.add_auth_session(session)
        self.db.commit()
        self.db.refresh(session)
        return raw_session_id, self._build_session_response(user, session)

    def get_session_response(self, raw_session_id: str) -> SessionResponse:
        session, user = self._get_valid_session(raw_session_id, require_access=True)
        self._touch_session(session)
        self.db.commit()
        self.db.refresh(session)
        return self._build_session_response(user, session)

    def probe_session(self, raw_session_id: str | None) -> SessionStatusResponse:
        """静默探测浏览器 session，用于前端恢复登录态。

        未登录、access 过期或 session 无效都返回 authenticated=False，不抛 401。
        若 access 过期但 idle 仍有效，则刷新短期访问有效期并返回 authenticated=True。
        """
        if not raw_session_id:
            return SessionStatusResponse(authenticated=False)
        try:
            session, user = self._get_valid_session(raw_session_id, require_access=True)
            self._touch_session(session)
            self.db.commit()
            self.db.refresh(session)
            return self._build_session_status_response(user, session, authenticated=True)
        except UnauthorizedError:
            try:
                refreshed = self.refresh_session(raw_session_id)
                return SessionStatusResponse(authenticated=True, **refreshed.model_dump())
            except UnauthorizedError:
                return SessionStatusResponse(authenticated=False)

    def authenticate_session_cookie(self, raw_session_id: str) -> AuthenticatedSubject:
        session, user = self._get_valid_session(raw_session_id, require_access=True)
        self._touch_session(session)
        self.db.commit()
        return AuthenticatedSubject(
            caller_type=CallerType.USER,
            user_id=user.id,
            org_unit_id=user.org_unit_id,
        )

    def refresh_session(self, raw_session_id: str) -> SessionResponse:
        session, user = self._get_valid_session(raw_session_id, require_access=False)
        settings = get_settings()
        now = datetime.now(timezone.utc)
        session.access_expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
        self._touch_session(session, now=now)
        self.repository.save_auth_session(session)
        self.db.commit()
        self.db.refresh(session)
        return self._build_session_response(user, session)

    def revoke_session(self, raw_session_id: str) -> None:
        session = self.repository.get_auth_session_by_hash(hash_session_id(raw_session_id))
        if session is None:
            return
        if session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            self.repository.save_auth_session(session)
            self.db.commit()

    def authenticate_user_token(self, token: str) -> AuthenticatedSubject:
        """验证用户 JWT token，返回 AuthenticatedSubject。

        解码 token 后重新检查用户和组织状态，验证 token_version。
        token 签发后被停用或 token_version 变更会导致认证失败。
        """
        try:
            claims = decode_access_token(token)
        except Exception:
            raise UnauthorizedError("token 无效或已过期")

        user = self.org_repository.get_user(claims["sub"])
        if user is None or user.status != ResourceStatus.ACTIVE:
            raise UnauthorizedError("用户不存在或已停用")
        if user.token_version != claims.get("token_version"):
            # 改密码、强制下线、管理员停用后旧 token 失效
            raise UnauthorizedError("token 已失效，请重新登录")

        org_unit = self.org_repository.get_org_unit(user.org_unit_id)
        if org_unit is None or org_unit.status != ResourceStatus.ACTIVE:
            raise UnauthorizedError("所属组织不存在或已停用")

        return AuthenticatedSubject(
            caller_type=CallerType.USER,
            user_id=user.id,
            org_unit_id=user.org_unit_id,
        )

    def refresh_access_token(self, _token: str) -> SessionResponse:
        """用未过期的 access token 换取新 token。

        重新检查用户/组织状态和 token_version。
        """
        raise UnauthorizedError("浏览器登录态已迁移到 session cookie")

    def _get_valid_session(
        self,
        raw_session_id: str,
        *,
        require_access: bool,
    ) -> tuple[AuthSession, UserAccount]:
        if not raw_session_id:
            raise UnauthorizedError("missing session")
        session = self.repository.get_auth_session_by_hash(hash_session_id(raw_session_id))
        if session is None:
            raise UnauthorizedError("session 无效或已过期")
        if session.revoked_at is not None:
            raise UnauthorizedError("session 已失效")

        now = datetime.now(timezone.utc)
        if self._as_utc(session.idle_expires_at) <= now:
            raise UnauthorizedError("session 已因长时间无操作失效")
        if require_access and self._as_utc(session.access_expires_at) <= now:
            raise UnauthorizedError("session 访问有效期已过期")

        user = self.org_repository.get_user(session.user_id)
        if user is None or user.status != ResourceStatus.ACTIVE:
            raise UnauthorizedError("用户不存在或已停用")
        if user.token_version != session.token_version:
            raise UnauthorizedError("session 已失效，请重新登录")

        org_unit = self.org_repository.get_org_unit(user.org_unit_id)
        if org_unit is None or org_unit.status != ResourceStatus.ACTIVE:
            raise UnauthorizedError("所属组织不存在或已停用")
        return session, user

    def _touch_session(self, session: AuthSession, *, now: datetime | None = None) -> None:
        settings = get_settings()
        current = now or datetime.now(timezone.utc)
        session.last_seen_at = current
        session.idle_expires_at = current + timedelta(minutes=settings.session_idle_expire_minutes)
        self.repository.save_auth_session(session)

    def _build_session_response(self, user: UserAccount, session: AuthSession) -> SessionResponse:
        status = self._build_session_status_response(user, session, authenticated=True)
        return SessionResponse(
            user=status.user,
            access_expires_at=status.access_expires_at,
            idle_expires_at=status.idle_expires_at,
            expires_in=status.expires_in,
            idle_expires_in=status.idle_expires_in,
        )

    def _build_session_status_response(
        self,
        user: UserAccount,
        session: AuthSession,
        *,
        authenticated: bool,
    ) -> SessionStatusResponse:
        org_unit = self.org_repository.get_org_unit(user.org_unit_id)
        now = datetime.now(timezone.utc)
        access_expires_at = self._as_utc(session.access_expires_at)
        idle_expires_at = self._as_utc(session.idle_expires_at)
        return SessionStatusResponse(
            authenticated=authenticated,
            user=UserSummary(
                id=user.id,
                name=user.name,
                phone=user.phone_normalized,
                org_unit_id=user.org_unit_id,
                org_unit_name=org_unit.name if org_unit else None,
                is_admin=self._has_admin_permission(user),
            ),
            access_expires_at=access_expires_at,
            idle_expires_at=idle_expires_at,
            expires_in=max(0, int((access_expires_at - now).total_seconds())),
            idle_expires_in=max(0, int((idle_expires_at - now).total_seconds())),
        )

    def _has_admin_permission(self, user: UserAccount) -> bool:
        subject = AuthenticatedSubject(
            caller_type=CallerType.USER,
            user_id=user.id,
            org_unit_id=user.org_unit_id,
        )
        try:
            self.assert_allowed(subject, ResourceType.API, "*", "manage")
        except ForbiddenError:
            return False
        return True

    @staticmethod
    def _hash_optional(value: str | None) -> str | None:
        if not value:
            return None
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
