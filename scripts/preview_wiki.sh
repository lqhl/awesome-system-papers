#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
port=${1:-8080}

if [[ ! "$port" =~ ^[0-9]+$ ]] || ((port < 1 || port > 65534)); then
  echo "错误：端口必须是 1 到 65534 之间的整数。" >&2
  exit 2
fi

if ! command -v tailscale >/dev/null 2>&1; then
  echo "错误：找不到 tailscale 命令；请先安装并登录 Tailscale。" >&2
  exit 1
fi

tailscale_ip=$(tailscale ip -4 2>/dev/null)
tailscale_ip=${tailscale_ip%%$'\n'*}
if [[ -z "$tailscale_ip" ]]; then
  echo "错误：没有可用的 Tailscale IPv4 地址；请先启动并登录 Tailscale。" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1 || ! command -v npx >/dev/null 2>&1; then
  echo "错误：找不到 npm/npx；Quartz 需要 Node.js 22 或更新版本。" >&2
  exit 1
fi

if [[ ! -d "$repo_root/quartz/node_modules" ]]; then
  echo "首次运行：正在安装 Quartz 依赖……"
  npm --prefix "$repo_root/quartz" ci
fi

ws_port=$((port + 1))
echo "本地预览：http://$tailscale_ip:$port"
echo "仅 Tailnet 内可访问；按 Ctrl-C 停止。"

cd "$repo_root/quartz"
exec npx --no-install quartz build --serve --watch \
  -d ../wiki \
  --host "$tailscale_ip" \
  --port "$port" \
  --wsPort "$ws_port"
