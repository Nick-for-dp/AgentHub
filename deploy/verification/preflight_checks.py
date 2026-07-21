"""Executable regression checks for deploy/scripts/profile_config.py.

Run with: python deploy/verification/preflight_checks.py
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from profile_config import (  # noqa: E402
    render_report,
    validate_frontend_payloads,
    validate_module_inventory,
    validate_profile_pair,
)


def valid_profiles() -> tuple[dict[str, str], dict[str, str]]:
    common = {
        "ENVIRONMENT": "production",
        "SERVER_HOST": "127.0.0.1",
        "AUTH_COOKIE_SECURE": "false",
        "AUTH_COOKIE_DOMAIN": "",
        "EMBED_ENABLED": "false",
        "EMBED_COOKIE_DOMAIN": "",
        "OBJECT_STORAGE_ENDPOINT": "http://minio.intra:9000",
        "LOG_LEVEL": "INFO",
    }
    external = {
        **common,
        "DEPLOYMENT_PROFILE": "external",
        "SERVER_PORT": "8240",
        "FRONTEND_PORT": "8080",
        "PUBLIC_ORIGIN": "http://10.20.30.40:8080",
        "DATABASE_URL": "mysql+pymysql://ext_user:ExtDbPassword123@mysql.intra:3306/agenthub?charset=utf8mb4",
        "REDIS_URL": "redis://redis.intra:6379/0",
        "API_KEY_SIGNING_SECRET": "external-api-signing-secret-000000000001",
        "AUTH_TOKEN_SECRET": "external-auth-token-secret-000000000001",
        "AUTH_COOKIE_NAME": "agenthub_session",
        "CORS_ALLOWED_ORIGINS": "http://10.20.30.40:8080",
        "EMBED_EXTERNAL_TOKEN_SECRET": "external-embed-secret-0000000000000001",
        "EMBED_SESSION_COOKIE_NAME": "agenthub_embed_session",
        "DIFY_API_KEY": "app-ext-dify-key-0001",
        "CONTRACT_REVIEW_DIFY_API_KEY": "",
        "OBJECT_STORAGE_ACCESS_KEY": "ext-minio-access-0001",
        "OBJECT_STORAGE_SECRET_KEY": "ext-minio-secret-0000000000000001",
        "OBJECT_STORAGE_BUCKET_RAW": "ext-agenthub-raw",
        "OBJECT_STORAGE_BUCKET_PARSED": "ext-agenthub-parsed",
        "MINIO_CORS_ALLOWED_ORIGINS": "http://10.20.30.40:8080",
        "SEED_ADMIN_PASSWORD": "ExtAdminPassword-0000000000000001",
        "RELEASE_ROOT": "/opt/agenthub/current-external",
        "PYTHON_BIN": "/opt/agenthub/venvs/external/bin/python",
        "FRONTEND_ROOT": "/opt/agenthub/frontend-dist/external/current",
        "JOURNAL_IDENTIFIER": "agenthub-external",
        "NGINX_ACCESS_LOG": "/var/log/nginx/agenthub-external.access.log",
        "NGINX_ERROR_LOG": "/var/log/nginx/agenthub-external.error.log",
    }
    internal = {
        **common,
        "DEPLOYMENT_PROFILE": "internal",
        "SERVER_PORT": "8241",
        "FRONTEND_PORT": "8081",
        "PUBLIC_ORIGIN": "http://10.20.30.40:8081",
        "DATABASE_URL": "mysql+pymysql://int_user:IntDbPassword123@mysql.intra:3306/agenthub_internal?charset=utf8mb4",
        "REDIS_URL": "redis://redis.intra:6379/1",
        "API_KEY_SIGNING_SECRET": "internal-api-signing-secret-000000000001",
        "AUTH_TOKEN_SECRET": "internal-auth-token-secret-000000000001",
        "AUTH_COOKIE_NAME": "agenthub_internal_session",
        "CORS_ALLOWED_ORIGINS": "http://10.20.30.40:8081",
        "INTERNAL_ALLOWED_CIDRS": "10.20.0.0/16,192.168.50.10/32",
        "EMBED_EXTERNAL_TOKEN_SECRET": "internal-embed-secret-0000000000000001",
        "EMBED_SESSION_COOKIE_NAME": "agenthub_internal_embed_session",
        "DIFY_API_KEY": "",
        "CONTRACT_REVIEW_DIFY_API_KEY": "app-int-contract-dify-key-0001",
        "OBJECT_STORAGE_ACCESS_KEY": "int-minio-access-0001",
        "OBJECT_STORAGE_SECRET_KEY": "int-minio-secret-0000000000000001",
        "OBJECT_STORAGE_BUCKET_RAW": "int-agenthub-raw",
        "OBJECT_STORAGE_BUCKET_PARSED": "int-agenthub-parsed",
        "MINIO_CORS_ALLOWED_ORIGINS": "http://10.20.30.40:8081",
        "SEED_ADMIN_PASSWORD": "IntAdminPassword-0000000000000001",
        "RELEASE_ROOT": "/opt/agenthub/current-internal",
        "PYTHON_BIN": "/opt/agenthub/venvs/internal/bin/python",
        "FRONTEND_ROOT": "/opt/agenthub/frontend-dist/internal/current",
        "JOURNAL_IDENTIFIER": "agenthub-internal",
        "NGINX_ACCESS_LOG": "/var/log/nginx/agenthub-internal.access.log",
        "NGINX_ERROR_LOG": "/var/log/nginx/agenthub-internal.error.log",
    }
    return external, internal


class PreflightChecks(unittest.TestCase):
    def assert_has_code(self, issues, code: str) -> None:
        self.assertIn(code, {issue.code for issue in issues})

    def test_valid_configuration(self) -> None:
        external, internal = valid_profiles()
        self.assertEqual(validate_profile_pair(external, internal), [])

    def test_port_conflict(self) -> None:
        external, internal = valid_profiles()
        internal["FRONTEND_PORT"] = external["FRONTEND_PORT"]
        self.assert_has_code(validate_profile_pair(external, internal), "PORT_CONFLICT")

    def test_cookie_conflict(self) -> None:
        external, internal = valid_profiles()
        internal["AUTH_COOKIE_NAME"] = external["AUTH_COOKIE_NAME"]
        self.assert_has_code(
            validate_profile_pair(external, internal), "COOKIE_NAME_CONFLICT"
        )

    def test_database_conflicts(self) -> None:
        external, internal = valid_profiles()
        internal["DATABASE_URL"] = external["DATABASE_URL"]
        issues = validate_profile_pair(external, internal)
        self.assert_has_code(issues, "DATABASE_URL_CONFLICT")
        self.assert_has_code(issues, "DATABASE_USER_CONFLICT")
        self.assert_has_code(issues, "DATABASE_SCHEMA_CONFLICT")

    def test_secret_reuse(self) -> None:
        external, internal = valid_profiles()
        internal["AUTH_TOKEN_SECRET"] = external["API_KEY_SIGNING_SECRET"]
        self.assert_has_code(validate_profile_pair(external, internal), "SECRET_REUSE")

    def test_bucket_conflict(self) -> None:
        external, internal = valid_profiles()
        internal["OBJECT_STORAGE_BUCKET_RAW"] = external["OBJECT_STORAGE_BUCKET_RAW"]
        self.assert_has_code(
            validate_profile_pair(external, internal), "BUCKET_CONFLICT"
        )

    def test_missing_internal_allowlist(self) -> None:
        external, internal = valid_profiles()
        internal["INTERNAL_ALLOWED_CIDRS"] = ""
        self.assert_has_code(
            validate_profile_pair(external, internal), "MISSING_ALLOWLIST"
        )

    def test_external_must_not_contain_fitz(self) -> None:
        issues = validate_module_inventory({"fitz"}, {"fitz", "docx"})
        self.assert_has_code(issues, "EXTERNAL_INTERNAL_DEPENDENCY")

    def test_internal_requires_pdf_and_docx_dependencies(self) -> None:
        issues = validate_module_inventory(set(), set())
        codes = [issue.code for issue in issues]
        self.assertEqual(codes.count("INTERNAL_DEPENDENCY_MISSING"), 2)

    def test_frontend_profile_isolation(self) -> None:
        self.assertEqual(
            validate_frontend_payloads(
                "LoginPage.js",
                "AgentHub 营销智能体",
                "ContractReviewPage.js\nRiskAssistantPage.js",
                "AgentHub 内部智能体",
            ),
            [],
        )
        issues = validate_frontend_payloads(
            "ContractReviewPage.js",
            "AgentHub 营销智能体 /internal/contract-review",
            "ContractReviewPage.js\nRiskAssistantPage.js",
            "AgentHub 内部智能体",
        )
        self.assert_has_code(issues, "EXTERNAL_INTERNAL_ASSET")
        self.assert_has_code(issues, "EXTERNAL_INTERNAL_MARKER")

    def test_report_never_contains_raw_sensitive_values(self) -> None:
        external, internal = valid_profiles()
        conflicting = copy.deepcopy(internal)
        conflicting["AUTH_TOKEN_SECRET"] = external["AUTH_TOKEN_SECRET"]
        conflicting["DATABASE_URL"] = external["DATABASE_URL"]
        report = render_report(validate_profile_pair(external, conflicting))
        sensitive_values = [
            external["AUTH_TOKEN_SECRET"],
            external["DATABASE_URL"],
            external["DIFY_API_KEY"],
            external["OBJECT_STORAGE_SECRET_KEY"],
            internal["CONTRACT_REVIEW_DIFY_API_KEY"],
        ]
        for value in sensitive_values:
            self.assertNotIn(value, report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
