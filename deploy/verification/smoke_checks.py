"""Local fixture tests for smoke_dual_profile.py.

Run with: python deploy/verification/smoke_checks.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SMOKE_SCRIPT = ROOT / "deploy" / "scripts" / "smoke_dual_profile.py"


class FixtureServer(ThreadingHTTPServer):
    def __init__(self, profile: str, *, fail_health: bool = False):
        super().__init__(("127.0.0.1", 0), FixtureHandler)
        self.profile = profile
        self.fail_health = fail_health


class FixtureHandler(BaseHTTPRequestHandler):
    server: FixtureServer

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _send(
        self,
        status: int,
        body: bytes,
        content_type: str = "text/plain",
        cookie: str = "",
    ):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        profile = self.server.profile
        if self.path == "/health":
            status = 503 if self.server.fail_health else 200
            self._send(status, b'{"status":"ok"}', "application/json")
        elif self.path == "/":
            self._send(
                200,
                b'<script type="module" src="/assets/login.js"></script>',
                "text/html",
            )
        elif self.path == "/assets/login.js":
            brand = (
                "AgentHub 营销智能体"
                if profile == "external"
                else "AgentHub 内部智能体"
            )
            self._send(200, brand.encode("utf-8"), "application/javascript")
        elif self.path == "/version.json":
            body = json.dumps(
                {"profile": profile, "revision": "fixture-revision"}
            ).encode()
            self._send(200, body, "application/json")
        elif self.path == "/api/v1/internal/contract-review/tasks/smoke-probe":
            self._send(
                404 if profile == "external" else 401, b'{"detail":"suppressed"}'
            )
        else:
            self._send(404, b"not found")

    def do_POST(self) -> None:  # noqa: N802
        profile = self.server.profile
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            self.rfile.read(length)
        if self.path == "/api/v1/auth/login":
            if profile == "external":
                cookie = (
                    "agenthub_session=external-cookie-value-secret; HttpOnly; Path=/"
                )
            else:
                cookie = "agenthub_internal_session=internal-cookie-value-secret; HttpOnly; Path=/"
            self._send(200, b'{"user":{"id":"fixture"}}', "application/json", cookie)
        elif self.path == "/api/v1/auth/logout":
            self._send(200, b'{"message":"ok"}', "application/json")
        else:
            self._send(404, b"not found")


class RunningFixture:
    def __init__(self, profile: str, *, fail_health: bool = False):
        self.server = FixtureServer(profile, fail_health=fail_health)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> FixtureServer:
        self.thread.start()
        return self.server

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def write_env(path: Path, profile: str, port: int) -> None:
    if profile == "external":
        cookie_name = "agenthub_session"
        phone = "+8613900000000"
        password = "ExternalFixturePasswordSecret"
        api_key = "external-api-key-secret"
    else:
        cookie_name = "agenthub_internal_session"
        phone = "+8613910000000"
        password = "InternalFixturePasswordSecret"
        api_key = "internal-api-key-secret"
    path.write_text(
        "\n".join(
            (
                f"DEPLOYMENT_PROFILE={profile}",
                f"PUBLIC_ORIGIN=http://127.0.0.1:{port}",
                f"AUTH_COOKIE_NAME={cookie_name}",
                f"SEED_ADMIN_PHONE={phone}",
                f"SEED_ADMIN_PASSWORD={password}",
                f"DIFY_API_KEY={api_key}",
            )
        ),
        encoding="utf-8",
    )


def run_fixture(
    *, fail_external_health: bool = False
) -> subprocess.CompletedProcess[str]:
    with RunningFixture(
        "external", fail_health=fail_external_health
    ) as external_server:
        with RunningFixture("internal") as internal_server:
            with tempfile.TemporaryDirectory() as temp_dir:
                external_env = Path(temp_dir) / "external.conf"
                internal_env = Path(temp_dir) / "internal.conf"
                write_env(external_env, "external", external_server.server_port)
                write_env(internal_env, "internal", internal_server.server_port)
                return subprocess.run(
                    [
                        sys.executable,
                        str(SMOKE_SCRIPT),
                        "--external-env",
                        str(external_env),
                        "--internal-env",
                        str(internal_env),
                        "--timeout",
                        "3",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )


class SmokeChecks(unittest.TestCase):
    def test_success_fixture(self) -> None:
        result = run_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dual-profile HTTP smoke passed", result.stdout)

    def test_failure_is_nonzero_and_secret_safe(self) -> None:
        result = run_fixture(fail_external_health=True)
        self.assertNotEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        for secret in (
            "ExternalFixturePasswordSecret",
            "InternalFixturePasswordSecret",
            "external-cookie-value-secret",
            "internal-cookie-value-secret",
            "external-api-key-secret",
            "internal-api-key-secret",
            "Authorization",
        ):
            self.assertNotIn(secret, combined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
