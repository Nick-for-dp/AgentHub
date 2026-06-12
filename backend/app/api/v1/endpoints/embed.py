from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedError
from app.db.session import get_db
from app.modules.auth.schemas import (
    EmbedRefreshRequest,
    EmbedRevokeRequest,
    EmbedRevokeResponse,
    EmbedSessionStatusResponse,
    EmbedTokenRequest,
    EmbedTokenResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter()


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise UnauthorizedError("missing authentication credentials")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("authorization must be bearer token")
    return token


def _require_embed_server_token(
    authorization: str | None,
    db: Session,
) -> None:
    raw_token = _extract_bearer_token(authorization)
    AuthService(db).verify_embed_server_token(raw_token)


@router.post("/token", response_model=EmbedTokenResponse)
def issue_embed_token(
    payload: EmbedTokenRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> EmbedTokenResponse:
    """官网用户登录后，由官网后端调用，签发 AgentHub embed access token。"""
    _require_embed_server_token(authorization, db)
    return AuthService(db).issue_embed_token(payload)


@router.post("/refresh", response_model=EmbedTokenResponse)
def refresh_embed_token(
    payload: EmbedRefreshRequest | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> EmbedTokenResponse:
    """embed access token 过期或即将过期时刷新。"""
    header_token = _extract_bearer_token(authorization) if authorization else None
    return AuthService(db).refresh_embed_token(payload or EmbedRefreshRequest(), header_token)


@router.get("/session", response_model=EmbedSessionStatusResponse)
def get_embed_session(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> EmbedSessionStatusResponse:
    """查询 AgentHub 侧 embed session 状态。"""
    header_token = _extract_bearer_token(authorization) if authorization else None
    return AuthService(db).get_embed_session_status(header_token)


@router.post("/revoke", response_model=EmbedRevokeResponse)
def revoke_embed_session(
    payload: EmbedRevokeRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> EmbedRevokeResponse:
    """官网用户登出时，由官网后端通知 AgentHub 撤销 embed session。"""
    _require_embed_server_token(authorization, db)
    return AuthService(db).revoke_embed_sessions(payload)
