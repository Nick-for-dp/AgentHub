#!/usr/bin/env bash
# Prepare two fixed virtual environments and two frontend builds from one checkout.

set -euo pipefail

usage() {
    echo "usage: $0 <repository-directory>" >&2
    exit 64
}

repo_dir="${1:-}"
[[ -n "$repo_dir" ]] || usage
[[ "$(id -u)" -eq 0 ]] || { echo "run as root" >&2; exit 77; }

repo_dir="$(realpath "$repo_dir")"
[[ -f "$repo_dir/backend/pyproject.toml" && -f "$repo_dir/frontend/package.json" ]] || usage

UV_BIN="${UV_BIN:-/usr/local/bin/uv}"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-/opt/agenthub/python}"
test -x "$UV_BIN"
command -v npm >/dev/null
id agenthub-external >/dev/null 2>&1
id agenthub-internal >/dev/null 2>&1

if command -v systemctl >/dev/null 2>&1; then
    for unit in agenthub-external.service agenthub-internal.service; do
        if systemctl is-active --quiet "$unit"; then
            echo "stop $unit before rebuilding fixed virtual environments" >&2
            exit 78
        fi
    done
fi

if git -C "$repo_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    [[ -z "$(git -C "$repo_dir" status --porcelain)" ]] || {
        echo "repository checkout must be clean" >&2
        exit 78
    }
    revision="$(git -C "$repo_dir" rev-parse --short=12 HEAD)"
else
    revision="manual"
fi

venv_root="/opt/agenthub/venvs"
install -d -o root -g root -m 0755 "$UV_PYTHON_INSTALL_DIR" "$venv_root"

sync_venv() {
    local profile="$1"
    local target="$venv_root/$profile"
    "$UV_BIN" venv --clear --python "$PYTHON_VERSION" "$target"
    if [[ "$profile" == internal ]]; then
        VIRTUAL_ENV="$target" "$UV_BIN" sync \
            --project "$repo_dir/backend" --active --frozen --no-dev \
            --no-install-project --extra internal
    else
        VIRTUAL_ENV="$target" "$UV_BIN" sync \
            --project "$repo_dir/backend" --active --frozen --no-dev \
            --no-install-project
    fi
}

sync_venv external
sync_venv internal

if "$venv_root/external/bin/python" -c 'import fitz' >/dev/null 2>&1; then
    echo "external venv unexpectedly contains PyMuPDF" >&2
    exit 1
fi
"$venv_root/internal/bin/python" -c 'import docx, fitz'

(
    cd "$repo_dir/frontend"
    npm ci
    npm run build:profiles
    npm run check:profile-builds
)

printf '{"profile":"external","revision":"%s"}\n' "$revision" \
    >"$repo_dir/frontend/dist/external/version.json"
printf '{"profile":"internal","revision":"%s"}\n' "$revision" \
    >"$repo_dir/frontend/dist/internal/version.json"

chown -R root:root "$venv_root" "$repo_dir/frontend/dist"
chmod a+rx /opt/agenthub "$repo_dir"
chmod -R a+rX \
    "$UV_PYTHON_INSTALL_DIR" "$venv_root" \
    "$repo_dir/backend" "$repo_dir/frontend/dist"
chmod -R go-w "$venv_root" "$repo_dir/frontend/dist"

echo "prepared AgentHub revision $revision in $repo_dir; services were not restarted"
