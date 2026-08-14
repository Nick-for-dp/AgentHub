"""初始化 AgentHub external 平台最小闭环数据。

用法：
    cd backend
    python -m scripts.seed
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import PRODUCTION_ENVIRONMENTS, Settings, get_settings
from app.core.enums import (
    APIKeyOwnerType,
    APIKeyStatus,
    AgentType,
    OrgUnitType,
    PolicyEffect,
    PublishStatus,
    ProviderType,
    ResourceType,
    RuntimeType,
    SubjectType,
    UserType,
    Visibility,
)
from app.core.exceptions import ConflictError
from app.core.security import generate_api_key_for_phone, normalize_phone
from app.db.session import get_db
from app.modules.agent.models import Agent
from app.modules.agent.schemas import AgentCreate, AgentKnowledgeBaseBind
from app.modules.agent.service import AgentService
from app.modules.auth.models import APIKey
from app.modules.auth.schemas import APIKeyCreateByPhone, PermissionPolicyCreate
from app.modules.auth.service import AuthService
from app.modules.knowledge.models import KnowledgeBase
from app.modules.knowledge.schemas import KnowledgeBaseCreate
from app.modules.knowledge.service import KnowledgeService
from app.modules.org.models import OrgUnit, UserAccount
from app.modules.org.schemas import OrgUnitCreate, UserCreate
from app.modules.org.service import OrgService


SEED_PLACEHOLDER_DIFY_KEY = "seed-placeholder-not-a-real-key"
DEFAULT_RUNTIME_APP_ID = "00000000-0000-0000-0000-000000000000"
DEFAULT_PROVIDER_KB_ID = "00000000-0000-0000-0000-000000000000"


@dataclass(frozen=True)
class SeedInputs:
    admin_phone: str
    admin_password: str
    external_phone: str
    external_password: str
    second_external_phone: str
    second_external_password: str
    marketing_runtime_app_id: str
    provider_kb_id: str
    marketing_dify_api_key: str

    @classmethod
    def from_settings(cls, settings: Settings) -> "SeedInputs":
        return cls(
            admin_phone=os.getenv("SEED_ADMIN_PHONE", "+8613900000000"),
            admin_password=os.getenv("SEED_ADMIN_PASSWORD", "Admin8Pass"),
            external_phone=os.getenv("SEED_EXT_PHONE", "+8613800001234"),
            external_password=os.getenv("SEED_EXT_PASSWORD", "Demo8Pass"),
            second_external_phone=os.getenv("SEED_EXT2_PHONE", "+8613800005678"),
            second_external_password=os.getenv("SEED_EXT2_PASSWORD", "Demo8Pass"),
            marketing_runtime_app_id=os.getenv(
                "SEED_RUNTIME_APP_ID",
                DEFAULT_RUNTIME_APP_ID,
            ),
            provider_kb_id=os.getenv("SEED_PROVIDER_KB_ID", DEFAULT_PROVIDER_KB_ID),
            marketing_dify_api_key=settings.dify_api_key or SEED_PLACEHOLDER_DIFY_KEY,
        )


@dataclass
class SeedSummary:
    admin_phone: str
    admin_key_prefix: str
    admin_key_raw: str | None = None
    external_phones: list[str] = field(default_factory=list)
    external_passwords: list[str] = field(default_factory=list)
    external_key_prefix: str | None = None
    external_key_raw: str | None = None
    agent_codes: list[str] = field(default_factory=list)
    knowledge_base_name: str | None = None


@dataclass(frozen=True)
class SeedServices:
    db: Session
    org: OrgService
    auth: AuthService
    agent: AgentService
    knowledge: KnowledgeService

    @classmethod
    def create(cls, db: Session) -> "SeedServices":
        return cls(
            db=db,
            org=OrgService(db),
            auth=AuthService(db),
            agent=AgentService(db),
            knowledge=KnowledgeService(db),
        )


def seed(*, db: Session | None = None, settings: Settings | None = None) -> SeedSummary:
    """初始化 external 平台种子数据，并返回不直接打印的结果摘要。"""
    resolved_settings = settings or get_settings()
    inputs = SeedInputs.from_settings(resolved_settings)
    db_generator = None
    if db is None:
        db_generator = get_db()
        db = next(db_generator)

    try:
        services = SeedServices.create(db)
        return _seed_external(services, inputs)
    finally:
        if db_generator is not None:
            db_generator.close()


def _seed_external(services: SeedServices, inputs: SeedInputs) -> SeedSummary:
    admin_user, admin_key, admin_key_raw = _seed_platform_admin(services, inputs)

    external_org = _get_or_create_org(
        services,
        name="测试外部客户",
        org_type=OrgUnitType.EXTERNAL_CUSTOMER,
    )
    external_user = _get_or_create_external_user(
        services,
        organization=external_org,
        name="张三",
        phone=inputs.external_phone,
        password=inputs.external_password,
    )
    second_external_user = _get_or_create_external_user(
        services,
        organization=external_org,
        name="李四",
        phone=inputs.second_external_phone,
        password=inputs.second_external_password,
    )
    external_key, external_key_raw = _get_or_create_external_key(
        services,
        external_user,
        inputs.external_phone,
    )
    marketing_agent = _get_or_create_marketing_agent(services, external_org, inputs)
    knowledge_base = _get_or_create_marketing_knowledge_base(
        services,
        external_org,
        inputs,
    )
    _bind_knowledge_base(services, marketing_agent, knowledge_base)
    _ensure_permission(
        services,
        subject_type=SubjectType.ORG_UNIT,
        subject_id=external_org.id,
        resource_type=ResourceType.AGENT,
        resource_id=marketing_agent.id,
        actions=["invoke"],
    )

    return SeedSummary(
        admin_phone=admin_user.phone_normalized or inputs.admin_phone,
        admin_key_prefix=admin_key.key_prefix,
        admin_key_raw=admin_key_raw,
        external_phones=[
            external_user.phone_normalized or inputs.external_phone,
            second_external_user.phone_normalized or inputs.second_external_phone,
        ],
        external_passwords=[inputs.external_password, inputs.second_external_password],
        external_key_prefix=external_key.key_prefix,
        external_key_raw=external_key_raw,
        agent_codes=[marketing_agent.code],
        knowledge_base_name=knowledge_base.name,
    )


def _seed_platform_admin(
    services: SeedServices,
    inputs: SeedInputs,
) -> tuple[UserAccount, APIKey, str | None]:
    organization = _get_or_create_org(
        services,
        name="AgentHub 运营",
        org_type=OrgUnitType.INTERNAL_COMPANY,
    )

    admin_user = next(
        (user for user in services.org.list_users() if user.email == "admin@agenthub.local"),
        None,
    )
    if admin_user is None:
        admin_user = services.org.create_user(
            UserCreate(
                org_unit_id=organization.id,
                name="管理员",
                user_type=UserType.INTERNAL_EMPLOYEE,
                email="admin@agenthub.local",
                phone=inputs.admin_phone,
                password=inputs.admin_password,
            )
        )

    admin_key, admin_key_raw = _get_or_create_admin_key(services, admin_user)
    _ensure_permission(
        services,
        subject_type=SubjectType.USER,
        subject_id=admin_user.id,
        resource_type=ResourceType.API,
        resource_id="*",
        actions=["manage"],
    )
    return admin_user, admin_key, admin_key_raw


def _get_or_create_org(
    services: SeedServices,
    *,
    name: str,
    org_type: OrgUnitType,
    parent_id: str | None = None,
) -> OrgUnit:
    existing = next(
        (
            org
            for org in services.org.list_org_units()
            if org.name == name and org.type == org_type and org.parent_id == parent_id
        ),
        None,
    )
    if existing is not None:
        return existing
    return services.org.create_org_unit(
        OrgUnitCreate(name=name, type=org_type, parent_id=parent_id)
    )


def _get_or_create_external_user(
    services: SeedServices,
    *,
    organization: OrgUnit,
    name: str,
    phone: str,
    password: str,
) -> UserAccount:
    normalized_phone = normalize_phone(phone)
    existing = next(
        (
            user
            for user in services.org.list_users()
            if user.user_type == UserType.EXTERNAL_CUSTOMER
            and user.phone_normalized == normalized_phone
        ),
        None,
    )
    if existing is not None:
        return existing
    return services.org.create_user(
        UserCreate(
            org_unit_id=organization.id,
            name=name,
            user_type=UserType.EXTERNAL_CUSTOMER,
            phone=phone,
            password=password,
        )
    )


def _get_or_create_external_key(
    services: SeedServices,
    user: UserAccount,
    fallback_phone: str,
) -> tuple[APIKey, str | None]:
    existing = next(
        (
            key
            for key in services.auth.list_api_keys()
            if key.issued_for_phone == user.phone_normalized and key.status == APIKeyStatus.ACTIVE
        ),
        None,
    )
    if existing is not None:
        return existing, None
    raw_key, record = services.auth.issue_external_customer_api_key_by_phone(
        APIKeyCreateByPhone(
            phone=user.phone or fallback_phone,
            name="MVP 演示 Key",
            scopes=["invoke", "read"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
    )
    return record, raw_key


def _get_or_create_admin_key(
    services: SeedServices,
    admin_user: UserAccount,
) -> tuple[APIKey, str | None]:
    existing = next(
        (
            key
            for key in services.auth.list_api_keys()
            if key.owner_type == APIKeyOwnerType.USER
            and key.owner_id == admin_user.id
            and key.status == APIKeyStatus.ACTIVE
        ),
        None,
    )
    if existing is not None:
        return existing, None

    generated = generate_api_key_for_phone("admin@agenthub.local")
    record = APIKey(
        key_prefix=generated.key_prefix,
        key_hash=generated.key_hash,
        owner_type=APIKeyOwnerType.USER,
        owner_id=admin_user.id,
        issued_for_phone=None,
        name="管理员 Key",
        scopes=["*"],
        status=APIKeyStatus.ACTIVE,
        expires_at=datetime.now(timezone.utc) + timedelta(days=365),
    )
    services.auth.repository.add_api_key(record)
    services.db.commit()
    services.db.refresh(record)
    return record, generated.raw_key


def _get_or_create_marketing_agent(
    services: SeedServices,
    owner: OrgUnit,
    inputs: SeedInputs,
) -> Agent:
    existing = next(
        (agent for agent in services.agent.list_agents() if agent.code == "qa"),
        None,
    )
    config = dict(existing.config_snapshot or {}) if existing else {}
    if inputs.marketing_dify_api_key != SEED_PLACEHOLDER_DIFY_KEY or not config.get("dify_api_key"):
        config["dify_api_key"] = inputs.marketing_dify_api_key
    config.setdefault("prompt_template", "")

    if existing is None:
        existing = services.agent.create_agent(
            AgentCreate(
                code="qa",
                name="营销智能体",
                type=AgentType.QA,
                description="面向外部客户的产品咨询与营销问答 Agent",
                owner_org_unit_id=owner.id,
                runtime_type=RuntimeType.DIFY,
                runtime_app_id=inputs.marketing_runtime_app_id,
                visibility=Visibility.EXTERNAL,
                config_snapshot=config,
            )
        )
    existing.name = "营销智能体"
    existing.type = AgentType.QA
    existing.description = "面向外部客户的产品咨询与营销问答 Agent"
    existing.owner_org_unit_id = owner.id
    existing.runtime_type = RuntimeType.DIFY
    existing.runtime_app_id = inputs.marketing_runtime_app_id
    existing.publish_status = PublishStatus.PUBLISHED
    existing.visibility = Visibility.EXTERNAL
    existing.config_snapshot = config
    services.db.add(existing)
    services.db.commit()
    services.db.refresh(existing)
    return existing


def _get_or_create_marketing_knowledge_base(
    services: SeedServices,
    owner: OrgUnit,
    inputs: SeedInputs,
) -> KnowledgeBase:
    existing = next(
        (
            knowledge_base
            for knowledge_base in services.knowledge.list_knowledge_bases()
            if knowledge_base.name == "MVP 知识库"
        ),
        None,
    )
    if existing is not None:
        return existing
    return services.knowledge.create_knowledge_base(
        KnowledgeBaseCreate(
            name="MVP 知识库",
            owner_org_unit_id=owner.id,
            provider=ProviderType.DIFY,
            provider_kb_id=inputs.provider_kb_id,
        )
    )


def _bind_knowledge_base(
    services: SeedServices,
    agent: Agent,
    knowledge_base: KnowledgeBase,
) -> None:
    try:
        services.agent.bind_knowledge_base(
            agent.id,
            AgentKnowledgeBaseBind(knowledge_base_id=knowledge_base.id, priority=100),
        )
    except ConflictError:
        services.db.rollback()


def _ensure_permission(
    services: SeedServices,
    *,
    subject_type: SubjectType,
    subject_id: str,
    resource_type: ResourceType,
    resource_id: str,
    actions: list[str],
) -> None:
    existing = next(
        (
            policy
            for policy in services.auth.list_permission_policies()
            if policy.subject_type == subject_type
            and policy.subject_id == subject_id
            and policy.resource_type == resource_type
            and policy.resource_id == resource_id
            and policy.effect == PolicyEffect.ALLOW
            and set(actions).issubset(set(policy.actions or []))
        ),
        None,
    )
    if existing is not None:
        return
    services.auth.create_permission_policy(
        PermissionPolicyCreate(
            subject_type=subject_type,
            subject_id=subject_id,
            resource_type=resource_type,
            resource_id=resource_id,
            actions=actions,
            effect=PolicyEffect.ALLOW,
        )
    )


def print_seed_summary(
    summary: SeedSummary,
    *,
    settings: Settings | None = None,
) -> None:
    resolved_settings = settings or get_settings()
    is_production = resolved_settings.environment.strip().lower() in PRODUCTION_ENVIRONMENTS

    print("种子数据创建完成。")
    print(f"  管理员手机: {summary.admin_phone}")
    if is_production:
        print(f"  管理员 API Key 前缀: {summary.admin_key_prefix}...")
    else:
        print(f"  管理员密码: {os.getenv('SEED_ADMIN_PASSWORD', 'Admin8Pass')} (仅本地演示)")
        if summary.admin_key_raw:
            print(f"  管理员 API Key (仅此一次): {summary.admin_key_raw}")
        else:
            print(f"  管理员 API Key 前缀: {summary.admin_key_prefix}...")

    for index, phone in enumerate(summary.external_phones, start=1):
        print(f"  外部客户 {index} 手机: {phone}")
        if not is_production and index <= len(summary.external_passwords):
            print(
                f"  外部客户 {index} 密码: {summary.external_passwords[index - 1]} (仅本地演示)"
            )
    if is_production or not summary.external_key_raw:
        print(f"  外部客户 API Key 前缀: {summary.external_key_prefix}...")
    else:
        print(f"  外部客户 API Key (仅此一次): {summary.external_key_raw}")
    if summary.knowledge_base_name:
        print(f"  KB name: {summary.knowledge_base_name}")

    print(f"  Agent codes: {', '.join(summary.agent_codes)}")


def main() -> int:
    settings = get_settings()
    summary = seed(settings=settings)
    print_seed_summary(summary, settings=settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
