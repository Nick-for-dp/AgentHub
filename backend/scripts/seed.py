"""种子数据脚本

为 MVP 演示环境创建最小闭环数据：
内部管理员 → 外部客户 → API Key → Agent → KB → 权限策略

幂等：已存在的数据跳过，可多次执行。

用法：cd backend && python scripts/seed.py

环境变量：
  SEED_DIFY_API_KEY    Agent 级 Dify API Key（可选，未设则用占位符）
  SEED_RUNTIME_APP_ID  Dify App ID（可选，未设则用占位符）
  SEED_PROVIDER_KB_ID  Dify 知识库 ID（可选，未设则用占位符）
  SEED_EXT_PHONE       外部客户手机号（可选，默认 +8613800001234）
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta, timezone

from app.core.enums import (
    APIKeyOwnerType,
    APIKeyStatus,
    AgentType,
    OrgUnitType,
    PolicyEffect,
    ProviderType,
    ResourceType,
    RuntimeType,
    SubjectType,
    UserType,
    Visibility,
)
from app.core.security import generate_api_key_for_phone
from app.db.session import get_db
from app.modules.agent.schemas import AgentCreate, AgentKnowledgeBaseBind
from app.modules.agent.service import AgentService
from app.modules.auth.models import APIKey
from app.modules.auth.schemas import APIKeyCreateByPhone, PermissionPolicyCreate
from app.modules.auth.service import AuthService
from app.modules.knowledge.schemas import KnowledgeBaseCreate
from app.modules.knowledge.service import KnowledgeService
from app.modules.org.schemas import OrgUnitCreate, UserCreate
from app.modules.org.service import OrgService

# ── Dify 集成配置（从环境变量读取）──────────────────────────
# 种子数据中不硬编码任何真实凭据。以下占位符值明显不是有效 Key，
# 种子执行后 Agent/KB 元数据会创建，但实际调用 Dify 时会因 Key 无效而失败。
_SEED_DIFY_API_KEY = os.getenv("SEED_DIFY_API_KEY", "seed-placeholder-not-a-real-key")
_SEED_RUNTIME_APP_ID = os.getenv("SEED_RUNTIME_APP_ID", "00000000-0000-0000-0000-000000000000")
_SEED_PROVIDER_KB_ID = os.getenv("SEED_PROVIDER_KB_ID", "00000000-0000-0000-0000-000000000000")
_SEED_EXT_PHONE = os.getenv("SEED_EXT_PHONE", "+8613800001234")
# 仅用于本地演示，生产环境必须通过安全渠道设置密码
_SEED_EXT_PASSWORD = os.getenv("SEED_EXT_PASSWORD", "Demo8Pass")


def seed() -> None:
    db = next(get_db())

    org_service = OrgService(db)
    auth_service = AuthService(db)
    agent_service = AgentService(db)
    knowledge_service = KnowledgeService(db)

    # ── 内部组织与管理员 ────────────────────────────────────
    internal_orgs = [o for o in org_service.list_org_units()
                     if o.name == "AgentHub 内部" and o.type == OrgUnitType.INTERNAL_COMPANY]
    if internal_orgs:
        internal_org = internal_orgs[0]
    else:
        internal_org = org_service.create_org_unit(
            OrgUnitCreate(name="AgentHub 内部", type=OrgUnitType.INTERNAL_COMPANY)
        )

    admin_depts = [o for o in org_service.list_org_units()
                   if o.name == "技术部" and o.type == OrgUnitType.INTERNAL_DEPARTMENT]
    if admin_depts:
        admin_dept = admin_depts[0]
    else:
        admin_dept = org_service.create_org_unit(
            OrgUnitCreate(
                name="技术部",
                type=OrgUnitType.INTERNAL_DEPARTMENT,
                parent_id=internal_org.id,
            )
        )

    admin_users = [u for u in org_service.list_users() if u.email == "admin@agenthub.local"]
    if admin_users:
        admin_user = admin_users[0]
    else:
        admin_user = org_service.create_user(
            UserCreate(
                org_unit_id=admin_dept.id,
                name="管理员",
                user_type=UserType.INTERNAL_EMPLOYEE,
                email="admin@agenthub.local",
            )
        )

    # ── 外部客户组织与用户 ─────────────────────────────────
    ext_orgs = [o for o in org_service.list_org_units()
                if o.name == "测试外部客户" and o.type == OrgUnitType.EXTERNAL_CUSTOMER]
    if ext_orgs:
        ext_org = ext_orgs[0]
    else:
        ext_org = org_service.create_org_unit(
            OrgUnitCreate(name="测试外部客户", type=OrgUnitType.EXTERNAL_CUSTOMER)
        )

    ext_users = [u for u in org_service.list_users()
                 if u.user_type == UserType.EXTERNAL_CUSTOMER and u.phone_normalized == _SEED_EXT_PHONE]
    if ext_users:
        ext_user = ext_users[0]
    else:
        ext_user = org_service.create_user(
            UserCreate(
                org_unit_id=ext_org.id,
                name="张三",
                user_type=UserType.EXTERNAL_CUSTOMER,
                phone=_SEED_EXT_PHONE,
                password=_SEED_EXT_PASSWORD,
            )
        )

    # ── API Key ─────────────────────────────────────────────
    # 外部客户 Key：通过手机号签发，用于 Q&A 调用
    issued_raw_key: str | None = None
    ext_keys = [k for k in auth_service.list_api_keys()
                if k.issued_for_phone == ext_user.phone_normalized and k.status == "ACTIVE"]
    if ext_keys:
        api_key_record = ext_keys[0]
        issued_raw_key = None
    else:
        raw_key, api_key_record = auth_service.issue_external_customer_api_key_by_phone(
            APIKeyCreateByPhone(
                phone=ext_user.phone or _SEED_EXT_PHONE,
                name="MVP 演示 Key",
                scopes=["invoke", "read"],
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            )
        )
        issued_raw_key = raw_key

    # 管理员 Key：内部管理员用于访问管理端
    admin_key_raw: str | None = None
    admin_keys = [k for k in auth_service.list_api_keys()
                  if k.owner_type == APIKeyOwnerType.USER
                  and k.owner_id == admin_user.id
                  and k.status == "ACTIVE"]
    if admin_keys:
        admin_key_record = admin_keys[0]
    else:
        # 管理员没有手机号（内部员工），用固定上下文直接生成 Key
        admin_generated = generate_api_key_for_phone("admin@agenthub.local")
        admin_key_record = APIKey(
            key_prefix=admin_generated.key_prefix,
            key_hash=admin_generated.key_hash,
            owner_type=APIKeyOwnerType.USER,
            owner_id=admin_user.id,
            issued_for_phone=None,  # 管理员不通过手机号签发
            name="管理员 Key",
            scopes=["*"],
            status=APIKeyStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
        auth_service.repository.add_api_key(admin_key_record)
        db.commit()
        db.refresh(admin_key_record)
        admin_key_raw = admin_generated.raw_key

    # ── Agent ───────────────────────────────────────────────
    agents = [a for a in agent_service.list_agents() if a.code == "qa"]
    if agents:
        agent = agents[0]
    else:
        # config_snapshot 中的 dify_api_key 来自环境变量 SEED_DIFY_API_KEY
        # 未配置时使用占位符，Agent 元数据可正常创建但调用 Dify 会失败
        agent = agent_service.create_agent(
            AgentCreate(
                code="qa",
                name="智能问答 Agent",
                type=AgentType.QA,
                description="MVP 演示用 Q&A Agent",
                owner_org_unit_id=ext_org.id,
                runtime_type=RuntimeType.DIFY,
                runtime_app_id=_SEED_RUNTIME_APP_ID,
                visibility=Visibility.EXTERNAL,
                config_snapshot={
                    "dify_api_key": _SEED_DIFY_API_KEY,
                    "prompt_template": "",
                },
            )
        )

    # ── 知识库 ──────────────────────────────────────────────
    kbs = [k for k in knowledge_service.list_knowledge_bases() if k.name == "MVP 知识库"]
    if kbs:
        kb = kbs[0]
    else:
        kb = knowledge_service.create_knowledge_base(
            KnowledgeBaseCreate(
                name="MVP 知识库",
                owner_org_unit_id=ext_org.id,
                provider=ProviderType.DIFY,
                provider_kb_id=_SEED_PROVIDER_KB_ID,
            )
        )

    # ── Agent-KB 绑定 ───────────────────────────────────────
    try:
        agent_service.bind_knowledge_base(
            agent.id,
            AgentKnowledgeBaseBind(knowledge_base_id=kb.id, priority=100),
        )
    except Exception:
        db.rollback()

    # ── 权限策略 ─────────────────────────────────────────────
    # 策略1：外部客户组织可 invoke Q&A Agent
    policies = [
        p for p in auth_service.list_permission_policies()
        if (p.subject_type == SubjectType.ORG_UNIT
            and p.subject_id == ext_org.id
            and p.resource_type == ResourceType.AGENT
            and p.resource_id == agent.id)
    ]
    if not policies:
        auth_service.create_permission_policy(
            PermissionPolicyCreate(
                subject_type=SubjectType.ORG_UNIT,
                subject_id=ext_org.id,
                resource_type=ResourceType.AGENT,
                resource_id=agent.id,
                actions=["invoke"],
                effect=PolicyEffect.ALLOW,
            )
        )

    # 策略2：管理员用户可 manage 所有 API 资源（管理端入口权限）
    admin_policies = [
        p for p in auth_service.list_permission_policies()
        if (p.subject_type == SubjectType.USER
            and p.subject_id == admin_user.id
            and p.resource_type == ResourceType.API)
    ]
    if not admin_policies:
        auth_service.create_permission_policy(
            PermissionPolicyCreate(
                subject_type=SubjectType.USER,
                subject_id=admin_user.id,
                resource_type=ResourceType.API,
                resource_id="*",  # "*" 表示所有 API 资源
                actions=["manage"],
                effect=PolicyEffect.ALLOW,
            )
        )

    phone = ext_user.phone_normalized
    key_prefix = api_key_record.key_prefix
    agent_code = agent.code
    kb_name = kb.name
    admin_prefix = admin_key_record.key_prefix

    db.close()

    print("种子数据创建完成。")
    print(f"  外部客户手机:    {phone}")
    print(f"  外部客户密码:    {_SEED_EXT_PASSWORD}  (仅本地演示)")
    if issued_raw_key:
        print(f"  外部客户 API Key (仅此一次): {issued_raw_key}")
    else:
        print(f"  外部客户 API Key 前缀:    {key_prefix}...")
    if admin_key_raw:
        print(f"  管理员 API Key (仅此一次): {admin_key_raw}")
    else:
        print(f"  管理员 API Key 前缀:    {admin_prefix}...")
    print(f"  Agent code:      {agent_code}")
    print(f"  KB name:         {kb_name}")


if __name__ == "__main__":
    seed()
