#!/usr/bin/env bash
# Run nginx -t using an installed binary or a temporarily extracted Ubuntu package.

set -euo pipefail

repo_root="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
work_dir="$(mktemp -d)"
created_default_log_dir=false
cleanup() {
    rm -rf "$work_dir"
    if [[ "$created_default_log_dir" == true ]]; then
        rmdir /var/log/nginx 2>/dev/null || true
    fi
}
trap cleanup EXIT

if [[ ! -d /var/log/nginx ]]; then
    [[ "$(id -u)" -eq 0 ]] || {
        echo "temporary nginx package verification requires root" >&2
        exit 77
    }
    install -d /var/log/nginx
    created_default_log_dir=true
fi

if command -v nginx >/dev/null 2>&1; then
    nginx_bin="$(command -v nginx)"
else
    (
        cd "$work_dir"
        apt-get download nginx-core >/dev/null
        dpkg-deb -x nginx-core_*.deb "$work_dir/nginx-package"
    )
    nginx_bin="$work_dir/nginx-package/usr/sbin/nginx"
fi

install -d "$work_dir/log" "$work_dir/temp/client" "$work_dir/temp/proxy"
install -d "$work_dir/temp/fastcgi" "$work_dir/temp/uwsgi" "$work_dir/temp/scgi"
printf 'allow 127.0.0.1/32;\n' >"$work_dir/internal-allowlist.conf"

sed \
    -e "s#/etc/agenthub/internal-allowlist.conf#$work_dir/internal-allowlist.conf#g" \
    -e "s#/var/log/nginx#$work_dir/log#g" \
    "$repo_root/deploy/nginx/agenthub-single-host.conf" >"$work_dir/site.conf"

cat >"$work_dir/nginx.conf" <<EOF
pid $work_dir/nginx.pid;
error_log stderr;
events { worker_connections 32; }
http {
    access_log off;
    client_body_temp_path $work_dir/temp/client;
    proxy_temp_path $work_dir/temp/proxy;
    fastcgi_temp_path $work_dir/temp/fastcgi;
    uwsgi_temp_path $work_dir/temp/uwsgi;
    scgi_temp_path $work_dir/temp/scgi;
    include $work_dir/site.conf;
}
EOF

"$nginx_bin" -t -p "$work_dir" -c "$work_dir/nginx.conf"
