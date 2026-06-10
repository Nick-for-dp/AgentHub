from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (
    agents,
    analytics,
    api_keys,
    audio,
    auth,
    chat,
    conversations,
    documents,
    evaluations,
    invocation_records,
    knowledge_bases,
    leads,
    org_units,
    permissions,
    users,
)
from app.modules.auth.dependencies import get_current_subject, require_admin_permission

api_router = APIRouter()

# auth 是公开接口，不需要 admin 权限
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# chat 是公开接口，不需要 admin 权限，但需要认证（由 endpoint 内部处理）
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])

# conversations 是用户产品会话接口，endpoint 内部要求 Cookie 用户会话。
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])

# audio 是语音转写/合成接口，endpoint 内部要求 Cookie Session 或 API Key。
api_router.include_router(audio.router, prefix="/audio", tags=["audio"])

# 所有 /admin/* 路由统一要求：
# 1. API Key 认证（get_current_subject）—— 验证"你是谁"
# 2. 管理权限授权（require_admin_permission）—— 验证"你能管理平台吗"
# 外部客户 Key 即使有效，也会因缺少管理权限策略而被拒绝。
_admin_deps = [Depends(get_current_subject), Depends(require_admin_permission)]
api_router.include_router(
    agents.router,
    prefix="/admin/agents",
    tags=["admin-agents"],
    dependencies=_admin_deps,
)
api_router.include_router(
    knowledge_bases.router,
    prefix="/admin/knowledge-bases",
    tags=["admin-knowledge-bases"],
    dependencies=_admin_deps,
)
api_router.include_router(
    documents.router,
    prefix="/admin/documents",
    tags=["admin-documents"],
    dependencies=_admin_deps,
)
api_router.include_router(
    org_units.router,
    prefix="/admin/org-units",
    tags=["admin-org-units"],
    dependencies=_admin_deps,
)
api_router.include_router(
    users.router,
    prefix="/admin/users",
    tags=["admin-users"],
    dependencies=_admin_deps,
)
api_router.include_router(
    api_keys.router,
    prefix="/admin/api-keys",
    tags=["admin-api-keys"],
    dependencies=_admin_deps,
)
api_router.include_router(
    permissions.router,
    prefix="/admin/permissions",
    tags=["admin-permissions"],
    dependencies=_admin_deps,
)
api_router.include_router(
    invocation_records.router,
    prefix="/admin/invocation-records",
    tags=["admin-invocation-records"],
    dependencies=_admin_deps,
)
api_router.include_router(
    leads.router,
    prefix="/admin/leads",
    tags=["admin-leads"],
    dependencies=_admin_deps,
)
api_router.include_router(
    analytics.router,
    prefix="/admin/analytics",
    tags=["admin-analytics"],
    dependencies=_admin_deps,
)
api_router.include_router(
    evaluations.router,
    prefix="/admin/evaluations",
    tags=["admin-evaluations"],
    dependencies=_admin_deps,
)
