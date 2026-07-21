#!/usr/bin/env python3
"""Run secret-safe configuration, dependency, and frontend checks."""

from __future__ import annotations

import argparse
import sys

from profile_config import (
    EnvFileError,
    load_profile_pair,
    render_report,
    validate_profile_pair,
    validate_runtime_artifacts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate AgentHub dual-profile deployment."
    )
    parser.add_argument("--external-env", default="/etc/agenthub/external.env")
    parser.add_argument("--internal-env", default="/etc/agenthub/internal.env")
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="validate environment files only; final deployment must run without this flag",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        external, internal = load_profile_pair(args.external_env, args.internal_env)
    except EnvFileError as exc:
        print(f"[FAIL] ENV_FILE: {exc}", file=sys.stderr)
        return 2

    issues = validate_profile_pair(external, internal)
    if not args.config_only:
        issues.extend(validate_runtime_artifacts(external, internal))
    print(render_report(issues))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
