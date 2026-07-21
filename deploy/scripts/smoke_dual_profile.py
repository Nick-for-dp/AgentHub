#!/usr/bin/env python3
"""Secret-safe HTTP smoke checks for the dual-profile entrypoints."""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
from dataclasses import dataclass
from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from profile_config import EnvFileError, load_profile_pair


ASSET_PATTERN = re.compile(
    r"[\"']((?:\./|/)?(?:assets/)?[A-Za-z0-9_.-]+\.(?:js|css))[\"']"
)
HTML_ASSET_PATTERN = re.compile(r"(?:src|href)=[\"']([^\"']+\.(?:js|css))[\"']")


class SmokeFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpResult:
    status: int
    headers: Message
    body: bytes


def http_request(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15,
    context: ssl.SSLContext | None = None,
) -> HttpResult:
    request = Request(url, data=body, method=method, headers=headers or {})
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            return HttpResult(
                response.status, response.headers, response.read(8 * 1024 * 1024)
            )
    except HTTPError as exc:
        return HttpResult(exc.code, exc.headers, exc.read(1024 * 1024))
    except (OSError, URLError) as exc:
        raise SmokeFailure("entrypoint is unreachable") from exc


def _origin(env: dict[str, str], profile: str) -> str:
    origin = env.get("PUBLIC_ORIGIN", "").strip().rstrip("/")
    parsed = urlsplit(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SmokeFailure(f"{profile} PUBLIC_ORIGIN is invalid")
    return origin


def _expect_status(result: HttpResult, expected: int, label: str) -> None:
    if result.status != expected:
        raise SmokeFailure(f"{label} returned unexpected status")


def _frontend_bundle(
    origin: str,
    *,
    timeout: float,
    context: ssl.SSLContext | None,
) -> str:
    queue = [f"{origin}/"]
    visited: set[str] = set()
    texts: list[str] = []
    origin_parts = urlsplit(origin)

    while queue:
        url = queue.pop(0)
        if url in visited:
            continue
        if len(visited) >= 200:
            raise SmokeFailure("frontend asset graph is unexpectedly large")
        visited.add(url)
        result = http_request("GET", url, timeout=timeout, context=context)
        _expect_status(result, 200, "frontend asset")
        text = result.body.decode("utf-8", errors="ignore")
        texts.append(text)

        candidates = set(HTML_ASSET_PATTERN.findall(text))
        candidates.update(ASSET_PATTERN.findall(text))
        for candidate in candidates:
            asset_url = urljoin(url, candidate)
            parsed = urlsplit(asset_url)
            if (
                parsed.scheme != origin_parts.scheme
                or parsed.netloc != origin_parts.netloc
            ):
                continue
            if not parsed.path.startswith("/assets/"):
                continue
            if parsed.path.endswith((".js", ".css")) and asset_url not in visited:
                queue.append(asset_url)
    return "\n".join(texts)


def _check_login_brand(
    profile: str,
    origin: str,
    expected_brand: str,
    *,
    timeout: float,
    context: ssl.SSLContext | None,
) -> None:
    payload = _frontend_bundle(origin, timeout=timeout, context=context)
    if expected_brand not in payload:
        raise SmokeFailure(f"{profile} login branding is missing")


def _check_version(
    profile: str,
    origin: str,
    *,
    timeout: float,
    context: ssl.SSLContext | None,
) -> str:
    result = http_request(
        "GET", f"{origin}/version.json", timeout=timeout, context=context
    )
    _expect_status(result, 200, f"{profile} version metadata")
    try:
        payload = json.loads(result.body)
    except json.JSONDecodeError as exc:
        raise SmokeFailure(f"{profile} version metadata is invalid") from exc
    if (
        payload.get("profile") != profile
        or not str(payload.get("revision", "")).strip()
    ):
        raise SmokeFailure(f"{profile} version metadata does not match the entrypoint")
    return str(payload["revision"])


def _login_cookie(
    profile: str,
    env: dict[str, str],
    origin: str,
    *,
    timeout: float,
    context: ssl.SSLContext | None,
) -> tuple[str, str]:
    phone = env.get("SEED_ADMIN_PHONE", "")
    password = env.get("SEED_ADMIN_PASSWORD", "")
    if not phone or not password:
        raise SmokeFailure(f"{profile} smoke login credentials are missing")
    body = json.dumps({"phone": phone, "password": password}).encode("utf-8")
    result = http_request(
        "POST",
        f"{origin}/api/v1/auth/login",
        body=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "agenthub-deploy-smoke",
        },
        timeout=timeout,
        context=context,
    )
    _expect_status(result, 200, f"{profile} login")
    expected_name = env.get("AUTH_COOKIE_NAME", "").strip()
    for header in result.headers.get_all("Set-Cookie", []):
        cookie_pair = header.split(";", 1)[0]
        name, separator, _ = cookie_pair.partition("=")
        if separator and name.strip() == expected_name:
            return expected_name, cookie_pair
    raise SmokeFailure(f"{profile} login did not set the expected auth cookie")


def _logout(
    origin: str,
    cookie_pair: str,
    *,
    timeout: float,
    context: ssl.SSLContext | None,
) -> None:
    # Best-effort cleanup. The cookie value remains in memory and is never logged.
    http_request(
        "POST",
        f"{origin}/api/v1/auth/logout",
        headers={"Cookie": cookie_pair, "User-Agent": "agenthub-deploy-smoke"},
        timeout=timeout,
        context=context,
    )


def run_smoke(
    external: dict[str, str],
    internal: dict[str, str],
    *,
    timeout: float = 15,
    context: ssl.SSLContext | None = None,
) -> None:
    external_origin = _origin(external, "external")
    internal_origin = _origin(internal, "internal")

    for profile, origin in (
        ("external", external_origin),
        ("internal", internal_origin),
    ):
        health = http_request(
            "GET", f"{origin}/health", timeout=timeout, context=context
        )
        _expect_status(health, 200, f"{profile} health")

    _check_login_brand(
        "external",
        external_origin,
        "AgentHub 营销智能体",
        timeout=timeout,
        context=context,
    )
    _check_login_brand(
        "internal",
        internal_origin,
        "AgentHub 内部智能体",
        timeout=timeout,
        context=context,
    )

    external_route = http_request(
        "GET",
        f"{external_origin}/api/v1/internal/contract-review/tasks/smoke-probe",
        timeout=timeout,
        context=context,
    )
    _expect_status(external_route, 404, "external internal API boundary")
    internal_route = http_request(
        "GET",
        f"{internal_origin}/api/v1/internal/contract-review/tasks/smoke-probe",
        timeout=timeout,
        context=context,
    )
    _expect_status(internal_route, 401, "internal unauthenticated API boundary")

    external_revision = _check_version(
        "external", external_origin, timeout=timeout, context=context
    )
    internal_revision = _check_version(
        "internal", internal_origin, timeout=timeout, context=context
    )
    if external_revision != internal_revision:
        raise SmokeFailure("entrypoints do not serve the same release revision")

    external_cookie_pair = ""
    internal_cookie_pair = ""
    try:
        external_cookie_name, external_cookie_pair = _login_cookie(
            "external", external, external_origin, timeout=timeout, context=context
        )
        internal_cookie_name, internal_cookie_pair = _login_cookie(
            "internal", internal, internal_origin, timeout=timeout, context=context
        )
        if external_cookie_name == internal_cookie_name:
            raise SmokeFailure("profile auth cookie names are not isolated")
    finally:
        if external_cookie_pair:
            _logout(
                external_origin, external_cookie_pair, timeout=timeout, context=context
            )
        if internal_cookie_pair:
            _logout(
                internal_origin, internal_cookie_pair, timeout=timeout, context=context
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test AgentHub dual-profile entrypoints."
    )
    parser.add_argument("--external-env", default="/etc/agenthub/external.env")
    parser.add_argument("--internal-env", default="/etc/agenthub/internal.env")
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--ca-file", help="CA bundle for internal-CA/IP-SAN HTTPS")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        external, internal = load_profile_pair(args.external_env, args.internal_env)
        context = (
            ssl.create_default_context(cafile=args.ca_file) if args.ca_file else None
        )
        run_smoke(external, internal, timeout=args.timeout, context=context)
    except (EnvFileError, SmokeFailure, ValueError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print("[OK] dual-profile HTTP smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
