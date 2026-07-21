#!/usr/bin/env bash
# Build and install one immutable source release plus isolated profile runtimes.

set -euo pipefail

usage() {
    echo "usage: $0 <source-directory> <revision>" >&2
    exit 64
}

source_dir="${1:-}"
revision="${2:-}"
[[ -n "$source_dir" && "$revision" =~ ^[A-Za-z0-9._-]+$ ]] || usage
[[ "$(id -u)" -eq 0 ]] || { echo "run as root" >&2; exit 77; }

source_dir="$(realpath "$source_dir")"
[[ -f "$source_dir/backend/pyproject.toml" && -f "$source_dir/frontend/package.json" ]] || usage

UV_BIN="${UV_BIN:-/usr/local/bin/uv}"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
command -v rsync >/dev/null
command -v npm >/dev/null
test -x "$UV_BIN"
id agenthub >/dev/null 2>&1

install_root="/opt/agenthub"
release_root="$install_root/releases/$revision"
venv_release_root="$install_root/venvs/releases"
frontend_release_root="$install_root/frontend-dist"

install -d -m 0755 "$install_root/releases" "$venv_release_root/external" "$venv_release_root/internal"
install -d -m 0755 "$frontend_release_root/external/releases" "$frontend_release_root/internal/releases"

if [[ ! -d "$release_root" ]]; then
    release_tmp="$install_root/releases/.${revision}.tmp.$$"
    rm -rf -- "$release_tmp"
    install -d -m 0755 "$release_tmp"
    rsync -a --delete \
        --exclude='.git/' \
        --exclude='.venv/' \
        --exclude='node_modules/' \
        --exclude='frontend/dist/' \
        --exclude='frontend/tmp/' \
        --exclude='backend/.env' \
        --exclude='frontend/.env' \
        "$source_dir/" "$release_tmp/"
    mv "$release_tmp" "$release_root"
fi

build_venv() {
    local profile="$1"
    local target="$venv_release_root/$profile/$revision"
    if [[ ! -d "$target" ]]; then
        "$UV_BIN" venv --python "$PYTHON_VERSION" "$target"
        if [[ "$profile" == internal ]]; then
            VIRTUAL_ENV="$target" "$UV_BIN" sync \
                --project "$release_root/backend" --active --frozen --no-dev \
                --no-install-project --extra internal
        else
            VIRTUAL_ENV="$target" "$UV_BIN" sync \
                --project "$release_root/backend" --active --frozen --no-dev \
                --no-install-project
        fi
    fi
}

build_venv external
build_venv internal

if "$venv_release_root/external/$revision/bin/python" -c 'import fitz' >/dev/null 2>&1; then
    echo "external venv unexpectedly contains PyMuPDF" >&2
    exit 1
fi
"$venv_release_root/internal/$revision/bin/python" -c 'import docx, fitz'

(
    cd "$release_root/frontend"
    npm ci
    npm run build:profiles
    npm run check:profile-builds
)

publish_frontend() {
    local profile="$1"
    local source="$release_root/frontend/dist/$profile"
    local releases="$frontend_release_root/$profile/releases"
    local target="$releases/$revision"
    if [[ ! -d "$target" ]]; then
        local tmp="$releases/.${revision}.tmp.$$"
        rm -rf -- "$tmp"
        install -d -m 0755 "$tmp"
        rsync -a --delete "$source/" "$tmp/"
        printf '{"profile":"%s","revision":"%s"}\n' "$profile" "$revision" >"$tmp/version.json"
        mv "$tmp" "$target"
    fi
    local next="$frontend_release_root/$profile/.current.$$"
    ln -s "releases/$revision" "$next"
    mv -Tf "$next" "$frontend_release_root/$profile/current"
}

switch_link() {
    local target="$1"
    local link="$2"
    local next="${link}.next.$$"
    ln -s "$target" "$next"
    mv -Tf "$next" "$link"
}

publish_frontend external
publish_frontend internal
switch_link "$release_root" "$install_root/current-external"
switch_link "$release_root" "$install_root/current-internal"
switch_link "$venv_release_root/external/$revision" "$install_root/venvs/external"
switch_link "$venv_release_root/internal/$revision" "$install_root/venvs/internal"

chown -R root:agenthub "$release_root" "$venv_release_root/external/$revision" \
    "$venv_release_root/internal/$revision" \
    "$frontend_release_root/external/releases/$revision" \
    "$frontend_release_root/internal/releases/$revision"
chmod -R o-w "$release_root" "$venv_release_root/external/$revision" \
    "$venv_release_root/internal/$revision" \
    "$frontend_release_root/external/releases/$revision" \
    "$frontend_release_root/internal/releases/$revision"

echo "installed AgentHub revision $revision; services were not restarted"
