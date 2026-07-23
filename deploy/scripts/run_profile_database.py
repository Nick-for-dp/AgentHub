#!/usr/bin/env python3
"""Safely migrate and/or seed one or both profile databases."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from profile_config import (
    EnvFileError,
    RUNTIME_PATHS,
    load_profile_pair,
    render_report,
    validate_database_targets,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run profile-scoped Alembic and seed commands."
    )
    parser.add_argument("--external-env", default="/etc/agenthub/external.env")
    parser.add_argument("--internal-env", default="/etc/agenthub/internal.env")
    parser.add_argument(
        "--profile", choices=("external", "internal", "both"), default="both"
    )
    parser.add_argument("--action", choices=("migrate", "seed", "all"), default="all")
    return parser.parse_args()


def _target_commands(
    profile: str, env: dict[str, str], action: str
) -> list[tuple[str, list[str], Path]]:
    release_root = Path(RUNTIME_PATHS[profile]["RELEASE_ROOT"])
    python_bin = Path(RUNTIME_PATHS[profile]["PYTHON_BIN"])
    backend_root = release_root / "backend"
    if not python_bin.is_file() or not (backend_root / "alembic.ini").is_file():
        raise RuntimeError(f"{profile} runtime paths are not installed")

    commands: list[tuple[str, list[str], Path]] = []
    if action in {"migrate", "all"}:
        commands.append(
            (
                "migration",
                [
                    str(python_bin),
                    "-m",
                    "alembic",
                    "-c",
                    str(backend_root / "alembic.ini"),
                    "upgrade",
                    "head",
                ],
                backend_root,
            )
        )
    if action in {"seed", "all"}:
        commands.append(
            (
                "seed",
                [
                    str(python_bin),
                    str(backend_root / "scripts" / "seed.py"),
                    "--profile",
                    profile,
                ],
                backend_root,
            )
        )
    return commands


def _run(
    label: str, profile: str, command: list[str], cwd: Path, env: dict[str, str]
) -> None:
    process_env = os.environ.copy()
    process_env.update(env)
    result = subprocess.run(
        command,
        cwd=cwd,
        env=process_env,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{profile} {label} failed; command output suppressed to protect secrets"
        )
    print(f"[OK] {profile} {label} completed")


def main() -> int:
    args = parse_args()
    try:
        external, internal = load_profile_pair(args.external_env, args.internal_env)
    except EnvFileError as exc:
        print(f"[FAIL] ENV_FILE: {exc}", file=sys.stderr)
        return 2

    issues = validate_database_targets(external, internal)
    if issues:
        print(render_report(issues), file=sys.stderr)
        return 1

    selected = ("external", "internal") if args.profile == "both" else (args.profile,)
    environments = {"external": external, "internal": internal}
    try:
        prepared = {
            profile: _target_commands(profile, environments[profile], args.action)
            for profile in selected
        }
        # For action=all, migrate every selected database before seeding either one.
        labels = (
            ("migration", "seed")
            if args.action == "all"
            else ("migration" if args.action == "migrate" else "seed",)
        )
        for label in labels:
            for profile in selected:
                for command_label, command, cwd in prepared[profile]:
                    if command_label == label:
                        _run(label, profile, command, cwd, environments[profile])
    except (RuntimeError, subprocess.SubprocessError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
