"""Semantic checks for checked-in systemd and Nginx dual-profile templates."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class TemplateChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.external_unit = (
            ROOT / "deploy/systemd/agenthub-external.service"
        ).read_text(encoding="utf-8")
        cls.internal_unit = (
            ROOT / "deploy/systemd/agenthub-internal.service"
        ).read_text(encoding="utf-8")
        cls.nginx = (ROOT / "deploy/nginx/agenthub-single-host.conf").read_text(
            encoding="utf-8"
        )
        cls.internal_env = (ROOT / "deploy/profiles/internal/.env.example").read_text(
            encoding="utf-8"
        )
        cls.seed_source = (ROOT / "backend/scripts/seed.py").read_text(encoding="utf-8")

    def test_external_unit_contract(self) -> None:
        for marker in (
            "EnvironmentFile=/etc/agenthub/external.env",
            "WorkingDirectory=/opt/agenthub/current-external/backend",
            "/opt/agenthub/venvs/external/bin/python",
            "--host 127.0.0.1 --port 8240",
            "SyslogIdentifier=agenthub-external",
        ):
            self.assertIn(marker, self.external_unit)
        self.assertNotIn("8241", self.external_unit)

    def test_internal_unit_contract(self) -> None:
        for marker in (
            "EnvironmentFile=/etc/agenthub/internal.env",
            "WorkingDirectory=/opt/agenthub/current-internal/backend",
            "/opt/agenthub/venvs/internal/bin/python",
            "--host 127.0.0.1 --port 8241",
            "SyslogIdentifier=agenthub-internal",
        ):
            self.assertIn(marker, self.internal_unit)
        self.assertNotIn("8240", self.internal_unit)

    def test_nginx_port_upstream_and_static_mapping(self) -> None:
        self.assertRegex(
            self.nginx,
            r"upstream agenthub_external_backend\s*\{[^}]*127\.0\.0\.1:8240;",
        )
        self.assertRegex(
            self.nginx,
            r"upstream agenthub_internal_backend\s*\{[^}]*127\.0\.0\.1:8241;",
        )
        for marker in (
            "listen 8080 default_server;",
            "root /opt/agenthub/frontend-dist/external/current;",
            "proxy_pass http://agenthub_external_backend;",
            "listen 8081 default_server;",
            "root /opt/agenthub/frontend-dist/internal/current;",
            "proxy_pass http://agenthub_internal_backend;",
        ):
            self.assertIn(marker, self.nginx)

    def test_internal_allowlist_fails_closed(self) -> None:
        include_index = self.nginx.index(
            "include /etc/agenthub/internal-allowlist.conf;"
        )
        deny_index = self.nginx.index("deny all;", include_index)
        self.assertGreater(deny_index, include_index)
        self.assertNotIn("allow 0.0.0.0/0", self.nginx)
        self.assertNotIn("allow ::/0", self.nginx)

    def test_streaming_and_long_request_proxy_settings(self) -> None:
        self.assertGreaterEqual(self.nginx.count("proxy_buffering off;"), 2)
        self.assertGreaterEqual(self.nginx.count("proxy_request_buffering off;"), 2)
        self.assertIn("proxy_read_timeout 600s;", self.nginx)
        self.assertIn("proxy_read_timeout 1800s;", self.nginx)
        self.assertGreaterEqual(
            self.nginx.count('proxy_set_header Accept-Encoding "";'), 2
        )

    def test_internal_contract_review_seed_variable_matches_seed_lookup(self) -> None:
        lookup = re.search(
            r'contract_review_runtime_app_id=os\.getenv\(\s*"(?P<name>[A-Z0-9_]+)"',
            self.seed_source,
        )
        self.assertIsNotNone(lookup)
        assert lookup is not None
        variable_name = lookup.group("name")
        self.assertRegex(self.internal_env, rf"(?m)^{re.escape(variable_name)}=")
        self.assertNotIn("SEED_CONTRACT_REVIEW_RUNTIME_APP_ID=", self.internal_env)


if __name__ == "__main__":
    unittest.main(verbosity=2)
