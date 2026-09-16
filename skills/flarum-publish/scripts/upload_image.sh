#!/usr/bin/env bash
# 转存图片到论坛图床（Flarum fof/upload 插件）
# 用法: upload_image.sh <图片URL|本地文件> [更多...]
# 环境变量: FLARUM_URL (必填), FLARUM_TOKEN (必填), FLARUM_USER_ID (可选), IS_CHINA (可选)
# 输出: 每个输入一行「<来源>\t<论坛图床URL>」，失败的行打印到 stderr 并以非 0 退出
# 注意: 输出的图床地址为「协议相对」形式（//host/path，不带 http:/https:），
#       可直接用于正文 ![](//host/path)；确需绝对地址时自行在前面补 https:
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
用法: upload_image.sh <图片URL|本地文件> [更多...]

示例:
  upload_image.sh https://raw.githubusercontent.com/owner/repo/main/assets/a.png
  upload_image.sh ./local.png https://example.com/b.jpg

输出: 每个输入一行「<来源>\t<论坛图床URL>」，图床地址为协议相对形式（//host/path）
EOF
  exit 1
}

[ $# -ge 1 ] || usage

: "${FLARUM_URL:?未设置 FLARUM_URL}"
: "${FLARUM_TOKEN:?未设置 FLARUM_TOKEN}"

AUTH="Authorization: Token ${FLARUM_TOKEN}"
if [ -n "${FLARUM_USER_ID:-}" ]; then
  AUTH="Authorization: Token ${FLARUM_TOKEN}; userId=${FLARUM_USER_ID}"
fi

MAX_BYTES=4194304   # 论坛限制 4096 kb，留一点余量

TMP_DOWNLOAD="$(mktemp -d)"
trap 'rm -rf "$TMP_DOWNLOAD"' EXIT

# GitHub raw 地址 → api.github.com 等价地址（raw 被墙/被代理阻断时的兜底）
raw_to_api() {
  python3 - "$1" <<'PY'
import re, sys
m = re.match(r'https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)$', sys.argv[1])
if not m:
    sys.exit(1)
owner, repo, ref, path = m.groups()
print(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}")
PY
}

# 下载图片到本地：$1=url $2=输出文件
fetch_image() {
  local url="$1" out="$2" api_url
  # 1) 直连
  if curl -fsSL --max-time 60 "$url" -o "$out" 2>/dev/null && [ -s "$out" ]; then
    return 0
  fi
  # 2) GitHub raw → api.github.com
  if api_url="$(raw_to_api "$url" 2>/dev/null)"; then
    if curl -fsSL --max-time 60 -H "Accept: application/vnd.github.raw" \
        "$api_url" -o "$out" 2>/dev/null && [ -s "$out" ]; then
      return 0
    fi
  fi
  # 3) 中国网络环境走代理前缀
  if [ "${IS_CHINA:-0}" = "1" ]; then
    if curl -fsSL --max-time 60 "https://filetas.asfd.cn/${url}" \
        -o "$out" 2>/dev/null && [ -s "$out" ]; then
      return 0
    fi
  fi
  return 1
}

upload_one() {
  local src="$1" file name mime size resp url

  if [ -f "$src" ]; then
    file="$src"
  else
    name="$(basename "${src%%\?*}")"
    [ -n "$name" ] || name="image"
    file="${TMP_DOWNLOAD}/${name}"
    if ! fetch_image "$src" "$file"; then
      echo "下载失败: $src" >&2
      return 1
    fi
  fi

  size="$(wc -c <"$file" | tr -d ' ')"
  if [ "$size" -gt "$MAX_BYTES" ]; then
    echo "文件过大（${size} 字节，上限 ${MAX_BYTES}）: $src" >&2
    return 1
  fi

  mime="$(file --mime-type -b "$file" 2>/dev/null || echo application/octet-stream)"

  # 注意：fof/upload 只认 files[] 这个字段名，用 image / file 会返回
  # 400 fof-upload.no_files_made_it_to_upload
  resp="$(curl -fsS -X POST "${FLARUM_URL}/api/fof/upload" \
    -H "$AUTH" -F "files[]=@${file};type=${mime}")" || {
    echo "上传失败: $src" >&2
    return 1
  }

  url="$(printf '%s' "$resp" | python3 -c '
import json, re, sys
doc = json.load(sys.stdin)
files = doc.get("data") or []
if not files:
    sys.exit(1)
u = files[0]["attributes"]["url"]
# 统一成协议相对形式：//host/path（正文里不需要 http:/https: 前缀）
u = re.sub(r"^https?:", "", u)
print(u if u.startswith("//") else "//" + u.lstrip("/"))
')" || {
    echo "响应解析失败: $src" >&2
    printf '%s\n' "$resp" >&2
    return 1
  }

  printf '%s\t%s\n' "$src" "$url"
}

status=0
for src in "$@"; do
  upload_one "$src" || status=1
done
exit "$status"
