"""
安全工具模块：手机号规范化、API Key 哈希/生成、常量时间比较、敏感数据脱敏、
密码哈希与 JWT 令牌签发。

手机号是外部客户的唯一业务锚点。平台通过手机号定位客户并签发 API Key。
API Key 本身必须使用加密安全随机数生成，平台只存储哈希值和短前缀，
绝不存储原始 Key，也不能用手机号直接作为密钥。

登录 token 由服务端密钥签名，包含过期时间和随机 jti。
密码只保存慢哈希，原文不得日志、响应或落库。
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import Response

from app.core.config import get_settings

# 手机号中可移除的分隔符：空格、括号、点、短横线
# 例如 "+86 138-0000-1234" → "+8613800001234"
PHONE_REMOVABLE_CHARS = re.compile(r"[\s().-]+")

# ── 敏感配置 Key 集合 ──────────────────────────────────────────
# 这些 Key 可能出现在 config_snapshot、日志、请求体等位置。
# 一旦发现这些 Key 的值，必须替换为 "***" 再输出到日志或外部系统。
# 新增敏感 Key 时在此集合中追加，不要在各处分散定义。
_SENSITIVE_KEY_PATTERNS: tuple[str, ...] = (
    "dify_api_key",
    "api_key",
    "key_hash",
    "secret",
    "token",
    "password",
    "authorization",
    "credential",
    "signing_secret",
)

# 以下 Key 出现在 DifyChatRequest.inputs 中时，必须在传给 Dify 之前剔除。
# 这些是平台自己的运行时配置，不是业务 inputs，不应发送到外部 runtime。
SENSITIVE_CONFIG_KEYS: frozenset[str] = frozenset({"dify_api_key"})


@dataclass(frozen=True)
class GeneratedAPIKey:
    raw_key: str
    key_prefix: str
    key_hash: str


def normalize_phone(phone: str) -> str:
    cleaned = PHONE_REMOVABLE_CHARS.sub("", phone.strip())
    if cleaned.startswith("+"):
        normalized = "+" + re.sub(r"\D", "", cleaned[1:])
    else:
        normalized = re.sub(r"\D", "", cleaned)
    if not normalized or normalized == "+":
        raise ValueError("phone is empty after normalization")
    # 11 位中国手机号（1 开头且不含国家码前缀）自动补 +86
    if not normalized.startswith("+") and len(normalized) == 11 and normalized.startswith("1"):
        normalized = "+86" + normalized
    return normalized


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_session_id() -> str:
    settings = get_settings()
    return secrets.token_urlsafe(settings.session_id_bytes)


def hash_session_id(raw_session_id: str) -> str:
    return hashlib.sha256(raw_session_id.encode("utf-8")).hexdigest()


def set_auth_cookie(response: Response, raw_session_id: str, max_age_seconds: int) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=raw_session_id,
        max_age=max_age_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.auth_cookie_name,
        domain=settings.auth_cookie_domain,
        path="/",
        samesite=settings.auth_cookie_samesite,
        secure=settings.auth_cookie_secure,
        httponly=True,
    )


def generate_api_key_for_phone(phone_normalized: str) -> GeneratedAPIKey:
    settings = get_settings()
    context = hmac.new(
        settings.api_key_signing_secret.encode("utf-8"),
        phone_normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:10]
    entropy = secrets.token_urlsafe(32)
    raw_key = f"ah_{context}_{entropy}"
    return GeneratedAPIKey(
        raw_key=raw_key,
        key_prefix=raw_key[:18],
        key_hash=hash_api_key(raw_key),
    )


def constant_time_equal(left: str, right: str) -> bool:
    """常量时间字符串比较，防止时序攻击探测 Key 前缀。"""
    return hmac.compare_digest(left, right)


def _is_sensitive_key(key: str) -> bool:
    """判断一个 Key 名称是否属于敏感配置。

    匹配逻辑：Key 的小写形式包含任一已知敏感模式子串。
    例如 "dify_api_key"、"my_api_key"、"auth_token" 都会命中。
    """
    key_lower = key.lower()
    return any(pattern in key_lower for pattern in _SENSITIVE_KEY_PATTERNS)


# ── 密码哈希 ──────────────────────────────────────────────────


def hash_password(password: str) -> str:
    """对密码进行 bcrypt 慢哈希，返回哈希字符串。"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, password_hash: str) -> bool:
    """校验明文密码与哈希值是否匹配。"""
    return bcrypt.checkpw(plain_password.encode(), password_hash.encode())


# ── JWT 令牌 ──────────────────────────────────────────────────


def create_access_token(
    *,
    sub: str,
    phone: str | None,
    org_unit_id: str,
    token_version: int = 0,
    expires_delta: timedelta | None = None,
) -> str:
    """签发短期 access token。

    Args:
        sub: 用户 ID
        phone: 规范化手机号（用于审计，非密钥材料）
        org_unit_id: 所属组织 ID
        token_version: 当前 token 版本号，做密码或停用后旧 token 失效
        expires_delta: 过期时长，默认使用配置中的 access_token_expire_minutes
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    payload = {
        "sub": sub,
        "phone": phone,
        "org_unit_id": org_unit_id,
        "typ": "access",
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + expires_delta,
        "token_version": token_version,
        "iss": settings.auth_token_issuer,
    }
    return jwt.encode(payload, settings.auth_token_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """解码并验证 access token。

    Returns:
        解码后的 claims dict，包含 sub、phone、org_unit_id、typ、jti、token_version 等字段。

    Raises:
        jwt.ExpiredSignatureError: token 已过期
        jwt.InvalidTokenError: token 签名无效、格式错误或 typ 不匹配
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.auth_token_secret,
        algorithms=["HS256"],
        issuer=settings.auth_token_issuer,
        options={"require": ["sub", "typ", "jti", "exp", "iat", "token_version"]},
    )
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("token type is not access")
    return payload


def sanitize_dict_for_log(data: Mapping[str, Any]) -> dict[str, Any]:
    """递归脱敏字典，将敏感字段的值替换为 '***'。

    用途：在 debug 日志中打印请求体、配置快照、SSE 数据等场景，
    确保不会意外泄漏 API Key、密钥、Token 等凭据。

    Args:
        data: 待脱敏的字典（可以是 dict 或任何 Mapping）

    Returns:
        脱敏后的 dict，原始 data 不会被修改

    Example:
        >>> sanitize_dict_for_log({"query": "hello", "inputs": {"dify_api_key": "secret"}})
        {"query": "hello", "inputs": {"dify_api_key": "***"}}
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        if _is_sensitive_key(key):
            # 敏感字段：直接替换为脱敏占位符
            result[key] = "***"
        elif isinstance(value, Mapping):
            # 嵌套字典：递归脱敏
            result[key] = sanitize_dict_for_log(value)
        elif isinstance(value, list):
            # 列表：逐个元素检查（列表中可能包含带敏感字段的字典）
            result[key] = [
                sanitize_dict_for_log(item) if isinstance(item, Mapping) else item
                for item in value
            ]
        else:
            # 普通值（字符串、数字等）：原样保留
            result[key] = value
    return result
