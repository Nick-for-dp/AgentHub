"""
认证与授权依赖：FastAPI 依赖注入函数，供 router 和 endpoint 使用。

认证（Authentication）回答"你是谁"：get_current_subject 从 HttpOnly Cookie
解析浏览器 Session，或从 HTTP Header 解析 Bearer API Key。

授权（Authorization）回答"你能做什么"：assert_allowed 根据主体和资源类型
检查权限策略；require_admin_permission 是管理端的统一授权入口。
"""

from fastapi import Depends, Header, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import ResourceType
from app.core.exceptions import UnauthorizedError
from app.core.security import set_auth_cookie
from app.db.session import get_db
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.auth.service import AuthService


def get_current_subject(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    x_agenthub_embed: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthenticatedSubject:
    """从 Cookie Session 或 Authorization Header 解析调用主体。

    认证步骤：
    1. 如果请求显式携带 Authorization Bearer，优先解析 Bearer 凭证
       （API Key 或官网嵌入 embed access token）
    2. 未携带 Bearer 时，浏览器请求读取 HttpOnly session cookie
    3. 返回统一 AuthenticatedSubject（含 caller_type、user_id、org_unit_id、scopes）

    Raises:
        UnauthorizedError: Cookie/Header 缺失、格式不对、凭证无效、凭证过期或被撤销
    """
    service = AuthService(db)
    settings = get_settings()
    raw_session_id = request.cookies.get(settings.auth_cookie_name)
    raw_embed_session_id = request.cookies.get(settings.embed_session_cookie_name)
    if authorization:
        # "Bearer <token>" → scheme="bearer", token="<token>"
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise UnauthorizedError("authorization must be bearer token")
        return service.authenticate_bearer_token(token)

    if x_agenthub_embed and x_agenthub_embed.lower() == "true":
        if not raw_embed_session_id:
            raise UnauthorizedError("missing embed session")
        return service.authenticate_embed_session_cookie(raw_embed_session_id)

    if not raw_session_id:
        if raw_embed_session_id:
            return service.authenticate_embed_session_cookie(raw_embed_session_id)
        raise UnauthorizedError("missing authentication credentials")
    subject = service.authenticate_session_cookie(raw_session_id)
    max_age_seconds = settings.session_idle_expire_minutes * 60
    set_auth_cookie(response, raw_session_id, max_age_seconds)
    return subject


def require_admin_permission(
    subject: AuthenticatedSubject = Depends(get_current_subject),
    db: Session = Depends(get_db),
) -> None:
    """验证调用者具有平台管理权限。

    所有 /admin/* 端点必须通过此依赖检查。
    检查逻辑：调用 AuthService.assert_allowed 验证 subject 是否有
    ResourceType.API 资源的 "manage" 操作权限。

    外部客户 Key 即使有效（能通过认证），如果没有 manage 权限策略，
    也会被此依赖拒绝，返回 403。

    Raises:
        ForbiddenError: 调用者没有管理权限
    """
    AuthService(db).assert_allowed(subject, ResourceType.API, "*", "manage")
