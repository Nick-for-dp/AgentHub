#!/usr/bin/env bash
# Verify unit syntax entirely inside a temporary directory.

set -euo pipefail

repo_root="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
work_dir="$(mktemp -d)"
trap 'rm -rf -- "$work_dir"' EXIT

install -d "$work_dir/repo/backend" "$work_dir/repo/deploy"
install -d "$work_dir/venvs/external/bin" "$work_dir/venvs/internal/bin"
install -d "$work_dir/etc/agenthub" "$work_dir/units"
install -m 0755 /bin/true "$work_dir/venvs/external/bin/python"
install -m 0755 /bin/true "$work_dir/venvs/internal/bin/python"
install -m 0644 "$repo_root/deploy/single-host-dual-profile.md" \
    "$work_dir/repo/deploy/single-host-dual-profile.md"
printf 'DEPLOYMENT_PROFILE=external\n' >"$work_dir/etc/agenthub/external.env"
printf 'DEPLOYMENT_PROFILE=internal\n' >"$work_dir/etc/agenthub/internal.env"

render_unit() {
    local source="$1"
    local target="$2"
    sed \
        -e "s#/opt/agenthub/repo#$work_dir/repo#g" \
        -e "s#/opt/agenthub/venvs#$work_dir/venvs#g" \
        -e "s#/etc/agenthub#$work_dir/etc/agenthub#g" \
        -e 's/^User=.*/User=root/' \
        -e 's/^Group=.*/Group=root/' \
        "$source" >"$target"
}

render_unit "$repo_root/deploy/systemd/agenthub-external.service" \
    "$work_dir/units/agenthub-external.service"
render_unit "$repo_root/deploy/systemd/agenthub-internal.service" \
    "$work_dir/units/agenthub-internal.service"

systemd-analyze verify \
    "$work_dir/units/agenthub-external.service" \
    "$work_dir/units/agenthub-internal.service"
