"""Shared, secret-safe validation for single-host dual-profile deployment."""

from __future__ import annotations

import ipaddress
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit


KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
COOKIE_PATTERN = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
PLACEHOLDER_MARKERS = (
    "change-me",
    "changeme",
    "replace-me",
    "replace-with",
    "placeholder",
    "example-secret",
    "your-secret",
    "<secret",
)
DOCUMENTATION_HOSTS = {"192.0.2.10", "198.51.100.10", "203.0.113.10"}

EXPECTED = {
    "external": {
        "SERVER_PORT": "8240",
        "FRONTEND_PORT": "8080",
    },
    "internal": {
        "SERVER_PORT": "8241",
        "FRONTEND_PORT": "8081",
    },
}

RUNTIME_PATHS = {
    "external": {
        "RELEASE_ROOT": "/opt/agenthub/repo",
        "PYTHON_BIN": "/opt/agenthub/venvs/external/bin/python",
        "FRONTEND_ROOT": "/opt/agenthub/repo/frontend/dist/external",
    },
    "internal": {
        "RELEASE_ROOT": "/opt/agenthub/repo",
        "PYTHON_BIN": "/opt/agenthub/venvs/internal/bin/python",
        "FRONTEND_ROOT": "/opt/agenthub/repo/frontend/dist/internal",
    },
}

REQUIRED_COMMON = (
    "DEPLOYMENT_PROFILE",
    "ENVIRONMENT",
    "SERVER_HOST",
    "SERVER_PORT",
    "FRONTEND_PORT",
    "PUBLIC_ORIGIN",
    "DATABASE_URL",
    "API_KEY_SIGNING_SECRET",
    "AUTH_TOKEN_SECRET",
    "AUTH_COOKIE_NAME",
    "CORS_ALLOWED_ORIGINS",
    "OBJECT_STORAGE_ENDPOINT",
    "OBJECT_STORAGE_ACCESS_KEY",
    "OBJECT_STORAGE_SECRET_KEY",
    "OBJECT_STORAGE_BUCKET_RAW",
    "OBJECT_STORAGE_BUCKET_PARSED",
    "MINIO_CORS_ALLOWED_ORIGINS",
)

SENSITIVE_FIELDS = (
    "API_KEY_SIGNING_SECRET",
    "AUTH_TOKEN_SECRET",
    "EMBED_EXTERNAL_TOKEN_SECRET",
    "DIFY_API_KEY",
    "CONTRACT_REVIEW_DIFY_API_KEY",
    "CONTRACT_REVIEW_FULL_CONTEXT_DIFY_API_KEY",
    "CONTRACT_REVIEW_BLOCK_LOOP_DIFY_API_KEY",
    "OBJECT_STORAGE_ACCESS_KEY",
    "OBJECT_STORAGE_SECRET_KEY",
    "RISK_DOCUMENT_PADDLEOCR_API_TOKEN",
    "RISK_DOCUMENT_QWEN_API_KEY",
    "SEED_ADMIN_PASSWORD",
    "SEED_EXT_PASSWORD",
    "SEED_EXT2_PASSWORD",
)


@dataclass(frozen=True)
class Issue:
    code: str
    field: str
    message: str


@dataclass(frozen=True)
class DatabaseTarget:
    url: str
    username: str
    database: str


class EnvFileError(ValueError):
    pass


def parse_env_file(path: str | Path) -> dict[str, str]:
    """Parse the EnvironmentFile subset used by AgentHub templates."""

    env_path = Path(path)
    values: dict[str, str] = {}
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EnvFileError(f"cannot read environment file: {env_path}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise EnvFileError(f"invalid environment assignment at line {line_number}")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not KEY_PATTERN.fullmatch(key):
            raise EnvFileError(f"invalid environment key at line {line_number}")
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key in values:
            raise EnvFileError(
                f"duplicate environment key at line {line_number}: {key}"
            )
        values[key] = value
    return values


def load_profile_pair(
    external_path: str | Path,
    internal_path: str | Path,
) -> tuple[dict[str, str], dict[str, str]]:
    return parse_env_file(external_path), parse_env_file(internal_path)


def _is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return not lowered or any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_port(
    profile: str, field: str, value: str | None
) -> tuple[int | None, list[Issue]]:
    try:
        port = int(value or "")
    except ValueError:
        return None, [
            Issue("INVALID_PORT", f"{profile}.{field}", "port must be an integer")
        ]
    if not 1 <= port <= 65535:
        return None, [
            Issue("INVALID_PORT", f"{profile}.{field}", "port is outside 1..65535")
        ]
    return port, []


def _database_target(
    profile: str, env: dict[str, str]
) -> tuple[DatabaseTarget | None, list[Issue]]:
    field = f"{profile}.DATABASE_URL"
    value = env.get("DATABASE_URL", "").strip()
    issues: list[Issue] = []
    if not value:
        return None, [Issue("MISSING_VALUE", field, "database URL is required")]
    if _is_placeholder(value):
        issues.append(
            Issue(
                "PLACEHOLDER_VALUE", field, "database URL still contains a placeholder"
            )
        )
    try:
        parsed = urlsplit(value)
        username = unquote(parsed.username or "")
        database = parsed.path.lstrip("/").split("/", 1)[0]
    except ValueError:
        return None, issues + [
            Issue("INVALID_DATABASE_URL", field, "database URL cannot be parsed")
        ]
    if (
        not parsed.scheme.startswith("mysql")
        or not parsed.hostname
        or not username
        or not database
    ):
        issues.append(
            Issue(
                "INVALID_DATABASE_URL",
                field,
                "database URL must contain MySQL scheme, host, username, and schema",
            )
        )
        return None, issues
    return DatabaseTarget(url=value, username=username, database=database), issues


def validate_database_targets(
    external: dict[str, str],
    internal: dict[str, str],
) -> list[Issue]:
    issues: list[Issue] = []
    if external.get("DEPLOYMENT_PROFILE", "").strip().lower() != "external":
        issues.append(
            Issue("PROFILE_MISMATCH", "external.DEPLOYMENT_PROFILE", "must be external")
        )
    if internal.get("DEPLOYMENT_PROFILE", "").strip().lower() != "internal":
        issues.append(
            Issue("PROFILE_MISMATCH", "internal.DEPLOYMENT_PROFILE", "must be internal")
        )

    external_db, external_issues = _database_target("external", external)
    internal_db, internal_issues = _database_target("internal", internal)
    issues.extend(external_issues)
    issues.extend(internal_issues)
    if external_db and internal_db:
        if external_db.url == internal_db.url:
            issues.append(
                Issue(
                    "DATABASE_URL_CONFLICT",
                    "DATABASE_URL",
                    "profiles use the same database URL",
                )
            )
        if external_db.username == internal_db.username:
            issues.append(
                Issue(
                    "DATABASE_USER_CONFLICT",
                    "DATABASE_URL",
                    "profiles use the same database user",
                )
            )
        if external_db.database == internal_db.database:
            issues.append(
                Issue(
                    "DATABASE_SCHEMA_CONFLICT",
                    "DATABASE_URL",
                    "profiles use the same database schema",
                )
            )
    return issues


def _validate_origin(
    profile: str, env: dict[str, str], frontend_port: int | None
) -> list[Issue]:
    issues: list[Issue] = []
    origin = env.get("PUBLIC_ORIGIN", "").strip().rstrip("/")
    field = f"{profile}.PUBLIC_ORIGIN"
    try:
        parsed = urlsplit(origin)
        origin_port = parsed.port
    except ValueError:
        parsed = None
        origin_port = None
    if (
        parsed is None
        or parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return [
            Issue(
                "INVALID_ORIGIN",
                field,
                "must be an absolute HTTP(S) origin without a path",
            )
        ]
    if parsed.hostname in DOCUMENTATION_HOSTS or parsed.hostname.endswith(".example"):
        issues.append(
            Issue("PLACEHOLDER_VALUE", field, "origin still uses a documentation host")
        )
    if origin_port is None:
        issues.append(
            Issue(
                "ORIGIN_PORT_MISSING",
                field,
                "origin must include the profile frontend port",
            )
        )
    elif frontend_port is not None and origin_port != frontend_port:
        issues.append(
            Issue(
                "ORIGIN_PORT_MISMATCH", field, "origin port differs from FRONTEND_PORT"
            )
        )

    for cors_field in ("CORS_ALLOWED_ORIGINS", "MINIO_CORS_ALLOWED_ORIGINS"):
        if origin not in {item.rstrip("/") for item in _split_csv(env.get(cors_field))}:
            issues.append(
                Issue(
                    "ORIGIN_NOT_ALLOWED",
                    f"{profile}.{cors_field}",
                    "must contain PUBLIC_ORIGIN including its port",
                )
            )

    secure = _parse_bool(env.get("AUTH_COOKIE_SECURE"))
    if secure is None:
        issues.append(
            Issue(
                "INVALID_BOOLEAN",
                f"{profile}.AUTH_COOKIE_SECURE",
                "must be true or false",
            )
        )
    elif parsed.scheme == "https" and not secure:
        issues.append(
            Issue(
                "INSECURE_HTTPS_COOKIE",
                f"{profile}.AUTH_COOKIE_SECURE",
                "must be true when PUBLIC_ORIGIN uses HTTPS",
            )
        )
    elif parsed.scheme == "http" and secure:
        issues.append(
            Issue(
                "UNUSABLE_HTTP_COOKIE",
                f"{profile}.AUTH_COOKIE_SECURE",
                "must be false for the explicitly approved HTTP trial",
            )
        )
    return issues


def _validate_internal_allowlist(internal: dict[str, str]) -> list[Issue]:
    field = "internal.INTERNAL_ALLOWED_CIDRS"
    values = _split_csv(internal.get("INTERNAL_ALLOWED_CIDRS"))
    if not values:
        return [
            Issue(
                "MISSING_ALLOWLIST",
                field,
                "at least one company LAN/VPN CIDR is required",
            )
        ]
    issues: list[Issue] = []
    for value in values:
        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError:
            issues.append(
                Issue("INVALID_ALLOWLIST", field, "contains a non-CIDR entry")
            )
            continue
        if network.prefixlen == 0:
            issues.append(
                Issue("OPEN_ALLOWLIST", field, "must not allow the entire Internet")
            )
    return issues


def _effective_cookie_name(profile: str, env: dict[str, str], *, embed: bool) -> str:
    if embed:
        default = (
            "agenthub_embed_session"
            if profile == "external"
            else "agenthub_internal_embed_session"
        )
        return env.get("EMBED_SESSION_COOKIE_NAME", default).strip()
    default = (
        "agenthub_session" if profile == "external" else "agenthub_internal_session"
    )
    return env.get("AUTH_COOKIE_NAME", default).strip()


def _validate_cookies(
    external: dict[str, str], internal: dict[str, str]
) -> list[Issue]:
    issues: list[Issue] = []
    active: list[tuple[str, str]] = []
    for profile, env in (("external", external), ("internal", internal)):
        auth_name = _effective_cookie_name(profile, env, embed=False)
        if not COOKIE_PATTERN.fullmatch(auth_name):
            issues.append(
                Issue(
                    "INVALID_COOKIE_NAME",
                    f"{profile}.AUTH_COOKIE_NAME",
                    "cookie name is empty or invalid",
                )
            )
        else:
            active.append((f"{profile}.AUTH_COOKIE_NAME", auth_name))
        if env.get("AUTH_COOKIE_DOMAIN", "").strip():
            issues.append(
                Issue(
                    "COOKIE_DOMAIN_NOT_HOST_ONLY",
                    f"{profile}.AUTH_COOKIE_DOMAIN",
                    "IP access requires an empty cookie domain",
                )
            )

        embed_enabled = _parse_bool(env.get("EMBED_ENABLED"))
        if embed_enabled is None:
            issues.append(
                Issue(
                    "INVALID_BOOLEAN",
                    f"{profile}.EMBED_ENABLED",
                    "must be true or false",
                )
            )
        elif embed_enabled:
            embed_name = _effective_cookie_name(profile, env, embed=True)
            if not COOKIE_PATTERN.fullmatch(embed_name):
                issues.append(
                    Issue(
                        "INVALID_COOKIE_NAME",
                        f"{profile}.EMBED_SESSION_COOKIE_NAME",
                        "cookie name is empty or invalid",
                    )
                )
            else:
                active.append((f"{profile}.EMBED_SESSION_COOKIE_NAME", embed_name))
            if env.get("EMBED_COOKIE_DOMAIN", "").strip():
                issues.append(
                    Issue(
                        "COOKIE_DOMAIN_NOT_HOST_ONLY",
                        f"{profile}.EMBED_COOKIE_DOMAIN",
                        "IP access requires an empty embed cookie domain",
                    )
                )
            if _is_placeholder(env.get("EMBED_EXTERNAL_TOKEN_SECRET", "")):
                issues.append(
                    Issue(
                        "PLACEHOLDER_VALUE",
                        f"{profile}.EMBED_EXTERNAL_TOKEN_SECRET",
                        "enabled embed requires a non-placeholder secret",
                    )
                )
            if profile == "internal" and not _split_csv(
                env.get("EMBED_ALLOWED_PARENT_ORIGINS")
            ):
                issues.append(
                    Issue(
                        "MISSING_EMBED_ALLOWLIST",
                        "internal.EMBED_ALLOWED_PARENT_ORIGINS",
                        "enabled internal embed requires explicit parent origins",
                    )
                )

    by_name: dict[str, list[str]] = {}
    for field, name in active:
        by_name.setdefault(name, []).append(field)
    for fields in by_name.values():
        if len(fields) > 1:
            issues.append(
                Issue(
                    "COOKIE_NAME_CONFLICT",
                    ",".join(fields),
                    "active cookie names must be unique",
                )
            )
    return issues


def _validate_buckets(
    external: dict[str, str], internal: dict[str, str]
) -> list[Issue]:
    issues: list[Issue] = []
    entries: list[tuple[str, str]] = []
    for profile, env, prefix in (
        ("external", external, "ext-"),
        ("internal", internal, "int-"),
    ):
        for key in ("OBJECT_STORAGE_BUCKET_RAW", "OBJECT_STORAGE_BUCKET_PARSED"):
            value = env.get(key, "").strip()
            field = f"{profile}.{key}"
            if not value:
                issues.append(Issue("MISSING_VALUE", field, "bucket name is required"))
            elif not value.startswith(prefix):
                issues.append(
                    Issue(
                        "BUCKET_NAMESPACE_MISMATCH",
                        field,
                        f"bucket must use the {prefix} namespace",
                    )
                )
            entries.append((field, value))
    by_value: dict[str, list[str]] = {}
    for field, value in entries:
        if value:
            by_value.setdefault(value, []).append(field)
    for fields in by_value.values():
        if len(fields) > 1:
            issues.append(
                Issue(
                    "BUCKET_CONFLICT", ",".join(fields), "bucket names must be unique"
                )
            )
    return issues


def _validate_secrets(
    external: dict[str, str], internal: dict[str, str]
) -> list[Issue]:
    issues: list[Issue] = []
    required = {
        "external": (
            "API_KEY_SIGNING_SECRET",
            "AUTH_TOKEN_SECRET",
            "DIFY_API_KEY",
            "OBJECT_STORAGE_ACCESS_KEY",
            "OBJECT_STORAGE_SECRET_KEY",
            "SEED_ADMIN_PASSWORD",
            "SEED_EXT_PASSWORD",
            "SEED_EXT2_PASSWORD",
        ),
        "internal": (
            "API_KEY_SIGNING_SECRET",
            "AUTH_TOKEN_SECRET",
            "CONTRACT_REVIEW_DIFY_API_KEY",
            "OBJECT_STORAGE_ACCESS_KEY",
            "OBJECT_STORAGE_SECRET_KEY",
            "SEED_ADMIN_PASSWORD",
        ),
    }
    for profile, env in (("external", external), ("internal", internal)):
        for key in required[profile]:
            value = env.get(key, "")
            if _is_placeholder(value):
                issues.append(
                    Issue(
                        "PLACEHOLDER_VALUE",
                        f"{profile}.{key}",
                        "required secret is missing or still a placeholder",
                    )
                )
        for key in ("API_KEY_SIGNING_SECRET", "AUTH_TOKEN_SECRET"):
            value = env.get(key, "").strip()
            if value and len(value) < 32:
                issues.append(
                    Issue(
                        "WEAK_SECRET",
                        f"{profile}.{key}",
                        "production secret must be at least 32 characters",
                    )
                )

    external_values = {
        value: key
        for key in SENSITIVE_FIELDS
        if (value := external.get(key, "").strip())
    }
    internal_values = {
        value: key
        for key in SENSITIVE_FIELDS
        if (value := internal.get(key, "").strip())
    }
    for value in sorted(set(external_values).intersection(internal_values)):
        issues.append(
            Issue(
                "SECRET_REUSE",
                f"external.{external_values[value]},internal.{internal_values[value]}",
                "profiles reuse the same sensitive credential",
            )
        )
    return issues


def validate_profile_pair(
    external: dict[str, str],
    internal: dict[str, str],
) -> list[Issue]:
    issues = validate_database_targets(external, internal)

    ports: dict[str, tuple[int | None, int | None]] = {}
    for profile, env in (("external", external), ("internal", internal)):
        for key in REQUIRED_COMMON:
            if not env.get(key, "").strip():
                issues.append(
                    Issue(
                        "MISSING_VALUE", f"{profile}.{key}", "required value is missing"
                    )
                )
        if env.get("ENVIRONMENT", "").strip().lower() not in {"prod", "production"}:
            issues.append(
                Issue(
                    "NON_PRODUCTION_MODE",
                    f"{profile}.ENVIRONMENT",
                    "deployment template must use production",
                )
            )
        if env.get("SERVER_HOST", "").strip() != "127.0.0.1":
            issues.append(
                Issue(
                    "BACKEND_NOT_LOOPBACK",
                    f"{profile}.SERVER_HOST",
                    "backend must bind 127.0.0.1",
                )
            )
        backend_port, backend_issues = _parse_port(
            profile, "SERVER_PORT", env.get("SERVER_PORT")
        )
        frontend_port, frontend_issues = _parse_port(
            profile, "FRONTEND_PORT", env.get("FRONTEND_PORT")
        )
        issues.extend(backend_issues)
        issues.extend(frontend_issues)
        ports[profile] = (backend_port, frontend_port)
        issues.extend(_validate_origin(profile, env, frontend_port))

        for key, expected_value in EXPECTED[profile].items():
            if env.get(key, "").strip() != expected_value:
                issues.append(
                    Issue(
                        "DEPLOYMENT_CONTRACT_MISMATCH",
                        f"{profile}.{key}",
                        "value differs from the checked-in systemd/Nginx deployment contract",
                    )
                )

    external_backend, external_frontend = ports.get("external", (None, None))
    internal_backend, internal_frontend = ports.get("internal", (None, None))
    if external_backend is not None and external_backend == internal_backend:
        issues.append(
            Issue("PORT_CONFLICT", "SERVER_PORT", "backend ports must differ")
        )
    if external_frontend is not None and external_frontend == internal_frontend:
        issues.append(
            Issue("PORT_CONFLICT", "FRONTEND_PORT", "frontend ports must differ")
        )

    if (
        external.get("REDIS_URL", "").strip()
        and external.get("REDIS_URL", "").strip()
        == internal.get("REDIS_URL", "").strip()
    ):
        issues.append(
            Issue(
                "REDIS_URL_CONFLICT",
                "REDIS_URL",
                "profiles must not share one Redis namespace",
            )
        )

    issues.extend(_validate_internal_allowlist(internal))
    issues.extend(_validate_cookies(external, internal))
    issues.extend(_validate_buckets(external, internal))
    issues.extend(_validate_secrets(external, internal))
    return issues


def probe_python_modules(python_bin: str) -> tuple[set[str], Issue | None]:
    path = Path(python_bin)
    field = str(path)
    if not path.is_file():
        return set(), Issue(
            "PYTHON_MISSING", field, "profile Python executable does not exist"
        )
    code = (
        "import importlib.util,json;"
        "names=('fitz','pymupdf','docx');"
        "print(json.dumps([name for name in names if importlib.util.find_spec(name)]))"
    )
    try:
        result = subprocess.run(
            [str(path), "-c", code],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        modules = set(json.loads(result.stdout))
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return set(), Issue(
            "PYTHON_PROBE_FAILED", field, "cannot inspect profile dependencies"
        )
    return modules, None


def validate_module_inventory(
    external_modules: set[str], internal_modules: set[str]
) -> list[Issue]:
    issues: list[Issue] = []
    if external_modules.intersection({"fitz", "pymupdf"}):
        issues.append(
            Issue(
                "EXTERNAL_INTERNAL_DEPENDENCY",
                "external.PYTHON_BIN",
                "external environment contains PyMuPDF",
            )
        )
    if not internal_modules.intersection({"fitz", "pymupdf"}):
        issues.append(
            Issue(
                "INTERNAL_DEPENDENCY_MISSING",
                "internal.PYTHON_BIN",
                "internal environment lacks PyMuPDF",
            )
        )
    if "docx" not in internal_modules:
        issues.append(
            Issue(
                "INTERNAL_DEPENDENCY_MISSING",
                "internal.PYTHON_BIN",
                "internal environment lacks python-docx",
            )
        )
    return issues


def _frontend_payload(root_value: str) -> tuple[str, str, list[Issue]]:
    root = Path(root_value)
    issues: list[Issue] = []
    if not (root / "index.html").is_file():
        issues.append(Issue("FRONTEND_MISSING", str(root), "index.html is missing"))
    if not (root / "version.json").is_file():
        issues.append(
            Issue("FRONTEND_VERSION_MISSING", str(root), "version.json is missing")
        )
    names: list[str] = []
    texts: list[str] = []
    if root.is_dir():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            names.append(path.name)
            if path.suffix.lower() in {".html", ".js", ".css", ".json"}:
                try:
                    texts.append(path.read_text(encoding="utf-8", errors="ignore"))
                except OSError:
                    issues.append(
                        Issue(
                            "FRONTEND_READ_FAILED",
                            str(root),
                            "cannot read frontend artifact",
                        )
                    )
                    break
    return "\n".join(names), "\n".join(texts), issues


def validate_frontend_payloads(
    external_names: str,
    external_text: str,
    internal_names: str,
    internal_text: str,
) -> list[Issue]:
    issues: list[Issue] = []
    for marker in ("ContractReviewPage", "RiskAssistantPage", "InternalLayout"):
        if marker in external_names:
            issues.append(
                Issue(
                    "EXTERNAL_INTERNAL_ASSET",
                    "external.FRONTEND_ROOT",
                    "external build contains an internal chunk",
                )
            )
            break
    for marker in ("/internal/contract-review", "合同审查工作台", "风控助手"):
        if marker in external_text:
            issues.append(
                Issue(
                    "EXTERNAL_INTERNAL_MARKER",
                    "external.FRONTEND_ROOT",
                    "external build contains internal UI text or routes",
                )
            )
            break
    if "AgentHub 营销智能体" not in external_text:
        issues.append(
            Issue(
                "FRONTEND_BRANDING_MISSING",
                "external.FRONTEND_ROOT",
                "external login branding is missing",
            )
        )
    if (
        "ContractReviewPage" not in internal_names
        or "RiskAssistantPage" not in internal_names
    ):
        issues.append(
            Issue(
                "INTERNAL_ASSET_MISSING",
                "internal.FRONTEND_ROOT",
                "internal workbench chunks are missing",
            )
        )
    if "AgentHub 内部智能体" not in internal_text:
        issues.append(
            Issue(
                "FRONTEND_BRANDING_MISSING",
                "internal.FRONTEND_ROOT",
                "internal login branding is missing",
            )
        )
    return issues


def validate_runtime_artifacts(
    external: dict[str, str],
    internal: dict[str, str],
) -> list[Issue]:
    issues: list[Issue] = []
    external_modules, external_probe_issue = probe_python_modules(
        RUNTIME_PATHS["external"]["PYTHON_BIN"]
    )
    internal_modules, internal_probe_issue = probe_python_modules(
        RUNTIME_PATHS["internal"]["PYTHON_BIN"]
    )
    if external_probe_issue:
        issues.append(external_probe_issue)
    if internal_probe_issue:
        issues.append(internal_probe_issue)
    if not external_probe_issue and not internal_probe_issue:
        issues.extend(validate_module_inventory(external_modules, internal_modules))

    external_names, external_text, external_frontend_issues = _frontend_payload(
        RUNTIME_PATHS["external"]["FRONTEND_ROOT"]
    )
    internal_names, internal_text, internal_frontend_issues = _frontend_payload(
        RUNTIME_PATHS["internal"]["FRONTEND_ROOT"]
    )
    issues.extend(external_frontend_issues)
    issues.extend(internal_frontend_issues)
    if not external_frontend_issues and not internal_frontend_issues:
        issues.extend(
            validate_frontend_payloads(
                external_names,
                external_text,
                internal_names,
                internal_text,
            )
        )
    return issues


def render_report(issues: list[Issue]) -> str:
    if not issues:
        return "[OK] dual-profile preflight passed"
    lines = ["[FAIL] dual-profile preflight found configuration/runtime problems"]
    for issue in issues:
        lines.append(f"[FAIL] {issue.code} ({issue.field}): {issue.message}")
    return "\n".join(lines)
