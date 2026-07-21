"""Equivalent local dual-instance acceptance using two MySQL schemas and one cookie jar.

This is a development-host check for task 7.4. It does not replace target-server
Nginx allowlist, Dify, MinIO, or real business workflow acceptance.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
PYTHON = BACKEND / ".venv" / "Scripts" / "python.exe"
NODE = Path(sys.executable).with_name("node.exe")
if not NODE.is_file():
    NODE = Path("node")

sys.path.insert(0, str(BACKEND))
from app.core.config import Settings  # noqa: E402


class AcceptanceFailure(RuntimeError):
    pass


def _profile_env(profile: str, database_url: str) -> dict[str, str]:
    is_external = profile == "external"
    frontend_port = "8080" if is_external else "8081"
    env = os.environ.copy()
    env.update(
        {
            "ENVIRONMENT": "production",
            "DEBUG": "false",
            "DEPLOYMENT_PROFILE": profile,
            "DATABASE_URL": database_url,
            "SERVER_HOST": "127.0.0.1",
            "SERVER_PORT": "8240" if is_external else "8241",
            "API_KEY_SIGNING_SECRET": secrets.token_urlsafe(48),
            "AUTH_TOKEN_SECRET": secrets.token_urlsafe(48),
            "AUTH_COOKIE_NAME": (
                "agenthub_session" if is_external else "agenthub_internal_session"
            ),
            "AUTH_COOKIE_SECURE": "false",
            "AUTH_COOKIE_SAMESITE": "lax",
            "AUTH_COOKIE_DOMAIN": "",
            "EMBED_ENABLED": "false",
            "CORS_ALLOWED_ORIGINS": f"http://127.0.0.1:{frontend_port}",
            "DIFY_BASE_URL": "http://127.0.0.1:9/v1",
            "DIFY_API_KEY": f"local-{profile}-dify-key",
            "CONTRACT_REVIEW_DIFY_API_KEY": f"local-{profile}-contract-key",
            "SEED_ADMIN_PHONE": ("+8613900000000" if is_external else "+8613910000000"),
            "SEED_ADMIN_PASSWORD": (
                "LocalExternal8Pass" if is_external else "LocalInternal8Pass"
            ),
            "SEED_EXT_PHONE": "+8613800001234",
            "SEED_EXT_PASSWORD": "LocalExternal8Demo",
            "SEED_EXT2_PHONE": "+8613800005678",
            "SEED_EXT2_PASSWORD": "LocalExternal9Demo",
            "SEED_RUNTIME_APP_ID": "local-marketing-app",
            "SEED_PROVIDER_KB_ID": "local-marketing-kb",
            "CONTRACT_REVIEW_RUNTIME_APP_ID": "local-contract-app",
        }
    )
    return env


def _run_checked(
    command: list[str], *, cwd: Path, env: dict[str, str], label: str
) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise AcceptanceFailure(f"{label} failed; subprocess output suppressed")


def _start_backend(profile: str, env: dict[str, str]) -> subprocess.Popen[bytes]:
    port = "8240" if profile == "external" else "8241"
    return subprocess.Popen(
        [
            str(PYTHON),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            port,
        ],
        cwd=BACKEND,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _start_frontend(profile: str) -> subprocess.Popen[bytes]:
    port = "8080" if profile == "external" else "8081"
    api_port = "8240" if profile == "external" else "8241"
    env = os.environ.copy()
    env.update(
        {
            "VITE_DEPLOYMENT_PROFILE": profile,
            "VITE_DEV_HOST": "127.0.0.1",
            "VITE_DEV_PORT": port,
            "VITE_API_HOST": "127.0.0.1",
            "VITE_API_PORT": api_port,
        }
    )
    vite = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
    return subprocess.Popen(
        [str(NODE), str(vite), "--host", "127.0.0.1", "--port", port, "--strictPort"],
        cwd=FRONTEND,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _opener(cookie_jar: http.cookiejar.CookieJar | None = None):
    handlers = [ProxyHandler({})]
    if cookie_jar is not None:
        handlers.append(HTTPCookieProcessor(cookie_jar))
    return build_opener(*handlers)


def _request_json(opener, method: str, url: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    try:
        with opener.open(
            Request(url, data=body, headers=headers, method=method), timeout=10
        ) as response:
            return json.loads(response.read())
    except (HTTPError, URLError, OSError, json.JSONDecodeError) as exc:
        raise AcceptanceFailure("HTTP acceptance request failed") from exc


def _wait_health(
    port: int, process: subprocess.Popen[bytes], timeout: float = 30
) -> None:
    opener = _opener()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AcceptanceFailure(f"process on port {port} exited during startup")
        try:
            payload = _request_json(opener, "GET", f"http://127.0.0.1:{port}/health")
            if payload.get("status") == "ok":
                return
        except AcceptanceFailure:
            time.sleep(0.25)
    raise AcceptanceFailure(f"health check on port {port} timed out")


def _wait_frontend(
    port: int, process: subprocess.Popen[bytes], timeout: float = 30
) -> None:
    opener = _opener()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AcceptanceFailure(f"frontend on port {port} exited during startup")
        try:
            with opener.open(f"http://127.0.0.1:{port}/", timeout=5) as response:
                if response.status == 200:
                    return
        except (HTTPError, URLError, OSError):
            time.sleep(0.25)
    raise AcceptanceFailure(f"frontend on port {port} timed out")


def _stop(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    if not PYTHON.is_file() or not (FRONTEND / "node_modules").is_dir():
        print(
            "[FAIL] local backend/frontend dependencies are not installed",
            file=sys.stderr,
        )
        return 1

    settings = Settings(_env_file=BACKEND / ".env")
    if not settings.test_database_url:
        print("[FAIL] TEST_DATABASE_URL is required", file=sys.stderr)
        return 1

    base_url = make_url(settings.test_database_url)
    server_url = base_url.set(database=None)
    suffix = f"{os.getpid()}_{int(time.time())}"
    databases = {
        "external": f"agenthub_dual_ext_{suffix}",
        "internal": f"agenthub_dual_int_{suffix}",
    }
    urls = {
        profile: base_url.set(database=name).render_as_string(hide_password=False)
        for profile, name in databases.items()
    }
    envs = {profile: _profile_env(profile, urls[profile]) for profile in databases}

    admin_engine = create_engine(server_url)
    processes: dict[str, subprocess.Popen[bytes] | None] = {
        "external_backend": None,
        "internal_backend": None,
        "external_frontend": None,
        "internal_frontend": None,
    }
    created: list[str] = []
    try:
        with admin_engine.begin() as connection:
            for database in databases.values():
                connection.execute(
                    text(
                        f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 "
                        "COLLATE utf8mb4_unicode_ci"
                    )
                )
                created.append(database)

        for profile in ("external", "internal"):
            _run_checked(
                [str(PYTHON), "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
                cwd=BACKEND,
                env=envs[profile],
                label=f"{profile} migration",
            )
            _run_checked(
                [str(PYTHON), "scripts/seed.py", "--profile", profile],
                cwd=BACKEND,
                env=envs[profile],
                label=f"{profile} seed",
            )

        processes["external_backend"] = _start_backend("external", envs["external"])
        processes["internal_backend"] = _start_backend("internal", envs["internal"])
        _wait_health(8240, processes["external_backend"])
        _wait_health(8241, processes["internal_backend"])
        processes["external_frontend"] = _start_frontend("external")
        processes["internal_frontend"] = _start_frontend("internal")
        _wait_frontend(8080, processes["external_frontend"])
        _wait_frontend(8081, processes["internal_frontend"])

        jar = http.cookiejar.CookieJar()
        browser = _opener(jar)
        _request_json(
            browser,
            "POST",
            "http://127.0.0.1:8080/api/v1/auth/login",
            {
                "phone": envs["external"]["SEED_ADMIN_PHONE"],
                "password": envs["external"]["SEED_ADMIN_PASSWORD"],
            },
        )
        _request_json(
            browser,
            "POST",
            "http://127.0.0.1:8081/api/v1/auth/login",
            {
                "phone": envs["internal"]["SEED_ADMIN_PHONE"],
                "password": envs["internal"]["SEED_ADMIN_PASSWORD"],
            },
        )
        cookie_names = {cookie.name for cookie in jar}
        if not {"agenthub_session", "agenthub_internal_session"}.issubset(cookie_names):
            raise AcceptanceFailure(
                "shared browser did not retain both profile cookies"
            )
        if not _request_json(
            browser, "GET", "http://127.0.0.1:8080/api/v1/auth/session"
        ).get("authenticated"):
            raise AcceptanceFailure("external session is not authenticated")
        if not _request_json(
            browser, "GET", "http://127.0.0.1:8081/api/v1/auth/session"
        ).get("authenticated"):
            raise AcceptanceFailure("internal session is not authenticated")

        _request_json(browser, "POST", "http://127.0.0.1:8080/api/v1/auth/logout")
        if _request_json(
            browser, "GET", "http://127.0.0.1:8080/api/v1/auth/session"
        ).get("authenticated"):
            raise AcceptanceFailure("external logout did not clear external session")
        if not _request_json(
            browser, "GET", "http://127.0.0.1:8081/api/v1/auth/session"
        ).get("authenticated"):
            raise AcceptanceFailure("external logout affected internal session")

        _request_json(
            browser,
            "POST",
            "http://127.0.0.1:8080/api/v1/auth/login",
            {
                "phone": envs["external"]["SEED_ADMIN_PHONE"],
                "password": envs["external"]["SEED_ADMIN_PASSWORD"],
            },
        )
        _stop(processes["internal_backend"])
        processes["internal_backend"] = None
        _wait_health(8240, processes["external_backend"])
        if not _request_json(
            browser, "GET", "http://127.0.0.1:8080/api/v1/auth/session"
        ).get("authenticated"):
            raise AcceptanceFailure("internal restart window affected external session")
        processes["internal_backend"] = _start_backend("internal", envs["internal"])
        _wait_health(8241, processes["internal_backend"])
        if not _request_json(
            browser, "GET", "http://127.0.0.1:8081/api/v1/auth/session"
        ).get("authenticated"):
            raise AcceptanceFailure("internal session did not survive backend restart")

        print("[OK] local dual-instance login/logout/restart isolation passed")
        return 0
    except AcceptanceFailure as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    finally:
        for process in processes.values():
            _stop(process)
        if created:
            with admin_engine.begin() as connection:
                for database in created:
                    connection.execute(text(f"DROP DATABASE IF EXISTS `{database}`"))
        admin_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
