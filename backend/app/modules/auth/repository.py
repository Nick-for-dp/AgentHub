from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.enums import ResourceStatus
from app.modules.auth.models import APIKey, AuthSession, EmbedSession, PermissionPolicy


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def add_api_key(self, api_key: APIKey) -> APIKey:
        self.db.add(api_key)
        self.db.flush()
        return api_key

    def add_auth_session(self, session: AuthSession) -> AuthSession:
        self.db.add(session)
        self.db.flush()
        return session

    def add_embed_session(self, session: EmbedSession) -> EmbedSession:
        self.db.add(session)
        self.db.flush()
        return session

    def get_auth_session_by_hash(self, session_hash: str) -> AuthSession | None:
        stmt = select(AuthSession).where(AuthSession.session_hash == session_hash)
        return self.db.scalars(stmt).one_or_none()

    def save_auth_session(self, session: AuthSession) -> AuthSession:
        self.db.add(session)
        self.db.flush()
        return session

    def save_embed_session(self, session: EmbedSession) -> EmbedSession:
        self.db.add(session)
        self.db.flush()
        return session

    def get_embed_session_by_hash(self, session_hash: str) -> EmbedSession | None:
        stmt = select(EmbedSession).where(EmbedSession.session_hash == session_hash)
        return self.db.scalars(stmt).one_or_none()

    def get_active_embed_session_by_external_user(
        self,
        *,
        external_user_id: str,
        agent_code: str,
    ) -> EmbedSession | None:
        stmt = (
            select(EmbedSession)
            .where(
                EmbedSession.external_user_id == external_user_id,
                EmbedSession.agent_code == agent_code,
                EmbedSession.status == ResourceStatus.ACTIVE,
            )
            .order_by(EmbedSession.created_at.desc())
            .limit(1)
        )
        return self.db.scalars(stmt).one_or_none()

    def list_active_embed_sessions_for_revoke(
        self,
        *,
        external_user_id: str | None,
        external_session_id: str | None,
    ) -> list[EmbedSession]:
        stmt = select(EmbedSession).where(EmbedSession.status == ResourceStatus.ACTIVE)
        if external_session_id:
            stmt = stmt.where(EmbedSession.external_session_id == external_session_id)
        elif external_user_id:
            stmt = stmt.where(EmbedSession.external_user_id == external_user_id)
        else:
            return []
        return list(self.db.scalars(stmt))

    def get_api_key_by_hash(self, key_hash: str) -> APIKey | None:
        stmt = select(APIKey).where(APIKey.key_hash == key_hash)
        return self.db.scalars(stmt).one_or_none()

    def mark_api_key_used(self, api_key: APIKey, used_at: datetime) -> APIKey:
        api_key.last_used_at = used_at
        self.db.add(api_key)
        self.db.flush()
        return api_key

    def list_api_keys(self, limit: int = 100, offset: int = 0) -> list[APIKey]:
        stmt = select(APIKey).order_by(APIKey.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def add_permission_policy(self, policy: PermissionPolicy) -> PermissionPolicy:
        self.db.add(policy)
        self.db.flush()
        return policy

    def list_active_policies_for_subjects(
        self,
        subjects: list[tuple[str, str]],
        resource_type: str,
        resource_id: str,
    ) -> list[PermissionPolicy]:
        if not subjects:
            return []
        stmt = select(PermissionPolicy).where(
            PermissionPolicy.status == ResourceStatus.ACTIVE,
            PermissionPolicy.resource_type == resource_type,
            PermissionPolicy.resource_id == resource_id,
        )
        subject_filters = [
            (PermissionPolicy.subject_type == subject_type)
            & (PermissionPolicy.subject_id == subject_id)
            for subject_type, subject_id in subjects
        ]
        stmt = stmt.where(or_(*subject_filters))
        return list(self.db.scalars(stmt))

    def list_permission_policies(self, limit: int = 100, offset: int = 0) -> list[PermissionPolicy]:
        stmt = select(PermissionPolicy).order_by(PermissionPolicy.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))
