from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import clear_embed_cookie, set_embed_cookie
from app.db.session import get_db
from app.modules.auth.schemas import (
    EmbedExchangeRequest,
    EmbedExchangeResponse,
    EmbedSessionStatusResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter()


@router.post("/exchange", response_model=EmbedExchangeResponse)
def exchange_embed_token(
    payload: EmbedExchangeRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> EmbedExchangeResponse:
    """使用产业互联网短期用户态 JWT 建立 AgentHub iframe embed session。"""
    raw_session_id, exchange_response = AuthService(db).exchange_embed_token(payload)
    set_embed_cookie(response, raw_session_id, exchange_response.expires_in)
    return exchange_response


@router.get("/session", response_model=EmbedSessionStatusResponse)
def get_embed_session(
    request: Request,
    db: Session = Depends(get_db),
) -> EmbedSessionStatusResponse:
    """查询当前 iframe embed session 状态，不返回产业互联网用户明细。"""
    raw_session_id = request.cookies.get(get_settings().embed_session_cookie_name)
    return AuthService(db).get_embed_session_status(raw_session_id)


@router.post("/logout")
def logout_embed_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """关闭 iframe 组件时撤销当前 AgentHub embed session 并清 Cookie。"""
    raw_session_id = request.cookies.get(get_settings().embed_session_cookie_name)
    revoked = AuthService(db).revoke_current_embed_session(raw_session_id)
    clear_embed_cookie(response)
    return {"revoked": revoked}
