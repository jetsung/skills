#!/usr/bin/env bash
# 获取 Flarum tags 列表并缓存到 ~/.cache/flarum_idev_tags
# 用法: fetch_tags.sh [--force]
# 环境变量: FLARUM_URL (必填), FLARUM_TOKEN (必填), FLARUM_USER_ID (可选)
set -euo pipefail

FORCE=false
[ "${1:-}" = "--force" ] && FORCE=true

TAGS_CACHE="${HOME}/.cache/flarum_idev_tags"

if [ "$FORCE" = false ] && [ -f "$TAGS_CACHE" ]; then
  echo "标签缓存已存在: $TAGS_CACHE（使用 --force 刷新）" >&2
  exit 0
fi

: "${FLARUM_URL:?未设置 FLARUM_URL}"
: "${FLARUM_TOKEN:?未设置 FLARUM_TOKEN}"

AUTH="Authorization: Token ${FLARUM_TOKEN}"
if [ -n "${FLARUM_USER_ID:-}" ]; then
  AUTH="Authorization: Token ${FLARUM_TOKEN}; userId=${FLARUM_USER_ID}"
fi

mkdir -p "$(dirname "$TAGS_CACHE")"

curl -fsS -H "$AUTH" "$FLARUM_URL/api/tags?include=parent" -o "$TAGS_CACHE" || {
  echo "获取标签列表失败" >&2
  exit 1
}

echo "标签缓存已保存: $TAGS_CACHE"
python3 - "$TAGS_CACHE" << 'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    doc = json.load(f)
tags = [t for t in doc.get("data", []) + doc.get("included", []) if t.get("type") == "tags"]
for t in tags:
    a = t.get("attributes", {})
    print("%4s  %-25s %s" % (t["id"], a.get("slug", ""), a.get("name", "")))
PYEOF
