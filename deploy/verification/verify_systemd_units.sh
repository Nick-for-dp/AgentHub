#!/usr/bin/env bash
# Verify unit syntax without requiring an installed AgentHub runtime.

set -euo pipefail

repo_root="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
[[ "$(id -u)" -eq 0 ]] || { echo "verification requires root" >&2; exit 77; }
[[ ! -e /opt/agenthub ]] || {
    echo "/opt/agenthub already exists; run systemd-analyze verify on the installed target instead" >&2
    exit 78
}

unit_dir="$(mktemp -d)"
cleanup() {
    rm -rf "$unit_dir" /opt/agenthub
}
trap cleanup EXIT

install -d /opt/agenthub/venvs/external/bin /opt/agenthub/venvs/internal/bin
install -d /opt/agenthub/current-external/backend /opt/agenthub/current-internal/backend
install -m 0755 /bin/true /opt/agenthub/venvs/external/bin/python
install -m 0755 /bin/true /opt/agenthub/venvs/internal/bin/python
install -m 0644 "$repo_root/deploy/systemd/agenthub-external.service" \
    "$unit_dir/agenthub-external.service"
install -m 0644 "$repo_root/deploy/systemd/agenthub-internal.service" \
    "$unit_dir/agenthub-internal.service"

systemd-analyze verify \
    "$unit_dir/agenthub-external.service" "$unit_dir/agenthub-internal.service"
