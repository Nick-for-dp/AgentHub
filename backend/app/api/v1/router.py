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
    embed,
    invocation_records,
    knowledge_bases,
    leads,
    org_units,
    permissions,
    users,
)
from app.api.v1.endpoints.internal import contract_review, file_parse, files, risk_assistant
from app.core.config import Settings, get_settings
from app.core.enums import DeploymentProfile
from app.modules.auth.dependencies import get_current_subject, require_admin_permission


def create_api_router(settings: Settings | None = None) -> APIRouter:
    """创建 API v1 路由表。

    Args:
        settings: 应用配置。测试可传入显式 Settings，生产启动默认读取环境变量。

    Returns:
        已按部署 profile 条件注册完成的 APIRouter。

    Boundary:
        ``/api/v1/internal/*`` 只在 internal profile 下注册，避免外部部署暴露内部
        合同审查、风控等接口契约。
    """
    resolved_settings = settings or get_settings()
    router = APIRouter()

    # auth 是公开接口，不需要 admin 权限
    router.include_router(auth.router, prefix="/auth", tags=["auth"])

    # embed 是官网嵌入问答的认证接口，由 endpoint 内部区分官网服务端 JWT 与 embed access token。
    router.include_router(embed.router, prefix="/embed", tags=["embed"])

    # chat 是公开接口，不需要 admin 权限，但需要认证（由 endpoint 内部处理）
    router.include_router(chat.router, prefix="/chat", tags=["chat"])

    # conversations 是用户产品会话接口，endpoint 内部要求 Cookie 用户会话。
    router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])

    # audio 是语音转写/合成接口，endpoint 内部要求 Cookie Session 或 API Key。
    router.include_router(audio.router, prefix="/audio", tags=["audio"])

    # 所有 /admin/* 路由统一要求：
    # 1. API Key 认证（get_current_subject）—— 验证"你是谁"
    # 2. 管理权限授权（require_admin_permission）—— 验证"你能管理平台吗"
    # 外部客户 Key 即使有效，也会因缺少管理权限策略而被拒绝。
    _admin_deps = [Depends(get_current_subject), Depends(require_admin_permission)]
    router.include_router(
        agents.router,
        prefix="/admin/agents",
        tags=["admin-agents"],
        dependencies=_admin_deps,
    )
    router.include_router(
        knowledge_bases.router,
        prefix="/admin/knowledge-bases",
        tags=["admin-knowledge-bases"],
        dependencies=_admin_deps,
    )
    router.include_router(
        documents.router,
        prefix="/admin/documents",
        tags=["admin-documents"],
        dependencies=_admin_deps,
    )
    router.include_router(
        org_units.router,
        prefix="/admin/org-units",
        tags=["admin-org-units"],
        dependencies=_admin_deps,
    )
    router.include_router(
        users.router,
        prefix="/admin/users",
        tags=["admin-users"],
        dependencies=_admin_deps,
    )
    router.include_router(
        api_keys.router,
        prefix="/admin/api-keys",
        tags=["admin-api-keys"],
        dependencies=_admin_deps,
    )
    router.include_router(
        permissions.router,
        prefix="/admin/permissions",
        tags=["admin-permissions"],
        dependencies=_admin_deps,
    )
    router.include_router(
        invocation_records.router,
        prefix="/admin/invocation-records",
        tags=["admin-invocation-records"],
        dependencies=_admin_deps,
    )
    router.include_router(
        leads.router,
        prefix="/admin/leads",
        tags=["admin-leads"],
        dependencies=_admin_deps,
    )
    router.include_router(
        analytics.router,
        prefix="/admin/analytics",
        tags=["admin-analytics"],
        dependencies=_admin_deps,
    )

    if resolved_settings.deployment_profile == DeploymentProfile.INTERNAL:
        router.include_router(
            files.router,
            prefix="/internal/files",
            tags=["internal-files"],
        )
        router.include_router(
            file_parse.router,
            prefix="/internal/file-parse",
            tags=["internal-file-parse"],
        )
        router.include_router(
            contract_review.router,
            prefix="/internal/contract-review",
            tags=["internal-contract-review"],
        )
        router.include_router(
            risk_assistant.router,
            prefix="/internal/risk-assistant",
            tags=["internal-risk-assistant"],
        )

    return router


api_router = create_api_router()
