"""认证端点：登录、查看当前用户、刷新 token、登出。"""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import clear_auth_cookie, set_auth_cookie
from app.db.session import get_db
from app.modules.auth.schemas import LoginRequest, SessionResponse, SessionStatusResponse
from app.modules.auth.service import AuthService

router = APIRouter()


def _get_raw_session_id(request: Request) -> str:
    settings = get_settings()
    raw_session_id = request.cookies.get(settings.auth_cookie_name)
    if not raw_session_id:
        raise UnauthorizedError("missing session")
    return raw_session_id


@router.post("/login", response_model=SessionResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """手机号 + 密码登录，创建服务端 session 并写入 HttpOnly Cookie。"""
    raw_session_id, session_response = AuthService(db).login_by_phone_password(
        payload,
        user_agent=request.headers.get("user-agent"),
        client_ip=request.client.host if request.client else None,
    )
    set_auth_cookie(response, raw_session_id, session_response.idle_expires_in)
    return session_response


@router.get("/me", response_model=SessionResponse)
def me(request: Request, response: Response, db: Session = Depends(get_db)):
    """返回当前 Cookie session 对应的用户与过期信息。"""
    session_response = AuthService(db).get_session_response(_get_raw_session_id(request))
    set_auth_cookie(response, _get_raw_session_id(request), session_response.idle_expires_in)
    return session_response


@router.get("/session", response_model=SessionStatusResponse)
def session_status(request: Request, response: Response, db: Session = Depends(get_db)):
    """静默探测当前浏览器 session，未登录时也返回 200。"""
    raw_session_id = request.cookies.get(get_settings().auth_cookie_name)
    status_response = AuthService(db).probe_session(raw_session_id)
    if raw_session_id and status_response.authenticated:
        set_auth_cookie(response, raw_session_id, status_response.idle_expires_in)
    elif raw_session_id:
        clear_auth_cookie(response)
    return status_response


@router.post("/refresh", response_model=SessionResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """刷新当前 Cookie session 的短期访问有效期。"""
    raw_session_id = _get_raw_session_id(request)
    session_response = AuthService(db).refresh_session(raw_session_id)
    set_auth_cookie(response, raw_session_id, session_response.idle_expires_in)
    return session_response


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """撤销当前 session 并清除浏览器 Cookie。"""
    raw_session_id = request.cookies.get(get_settings().auth_cookie_name)
    if raw_session_id:
        AuthService(db).revoke_session(raw_session_id)
    clear_auth_cookie(response)
    return {"message": "ok"}
