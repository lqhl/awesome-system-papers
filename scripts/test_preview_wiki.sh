#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

mkdir -p "$tmp_dir/bin"
cat >"$tmp_dir/bin/tailscale" <<'EOF'
#!/usr/bin/env bash
if [[ "$*" == "ip -4" ]]; then
  printf '%s\n' "100.64.0.42"
else
  exit 2
fi
EOF
cat >"$tmp_dir/bin/npx" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$PWD" >"$PREVIEW_TEST_DIR/npx.cwd"
printf '%s\n' "$@" >"$PREVIEW_TEST_DIR/npx.args"
EOF
chmod +x "$tmp_dir/bin/tailscale" "$tmp_dir/bin/npx"

output=$(PATH="$tmp_dir/bin:$PATH" PREVIEW_TEST_DIR="$tmp_dir" \
  "$repo_root/scripts/preview_wiki.sh" 8787)

[[ "$output" == *"http://100.64.0.42:8787"* ]]
[[ "$(cat "$tmp_dir/npx.cwd")" == "$repo_root/quartz" ]]
diff -u <(printf '%s\n' --no-install quartz build --serve --watch -d ../wiki --host 100.64.0.42 --port 8787 --wsPort 8788) \
  "$tmp_dir/npx.args"

if PATH="$tmp_dir/bin:$PATH" PREVIEW_TEST_DIR="$tmp_dir" \
  "$repo_root/scripts/preview_wiki.sh" invalid >"$tmp_dir/invalid.out" 2>&1; then
  echo "expected an invalid port to fail" >&2
  exit 1
fi
grep -q "端口必须" "$tmp_dir/invalid.out"

echo "preview_wiki tests passed"
