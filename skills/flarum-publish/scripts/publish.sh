#!/usr/bin/env bash
# 发布文章到 Flarum 论坛
# 用法: publish.sh <标题> <正文文件|-> [标签1,标签2]
# 环境变量: FLARUM_URL (必填), FLARUM_TOKEN (必填), FLARUM_USER_ID (可选)
set -euo pipefail

usage() {
  echo "用法: $0 <标题> <正文文件|-> [标签1,标签2]" >&2
  exit 1
}

[ $# -ge 2 ] || usage

TITLE="$1"
CONTENT_FILE="$2"
TAGS_INPUT="${3:-}"

: "${FLARUM_URL:?未设置 FLARUM_URL}"
: "${FLARUM_TOKEN:?未设置 FLARUM_TOKEN}"

AUTH="Authorization: Token ${FLARUM_TOKEN}"
if [ -n "${FLARUM_USER_ID:-}" ]; then
  AUTH="Authorization: Token ${FLARUM_TOKEN}; userId=${FLARUM_USER_ID}"
fi

# 读取正文
if [ "$CONTENT_FILE" = "-" ]; then
  CONTENT="$(cat)"
else
  CONTENT="$(cat "$CONTENT_FILE")"
fi

# 构造 JSON（python3 处理转义）
make_json() {
  # $1 = tags 数组 JSON（如 '[{"type":"tags","id":"1"}]'）或空
  python3 -c '
import json, sys
tags = json.loads(sys.argv[1]) if sys.argv[1] else None
data = {
    "type": "discussions",
    "attributes": {"title": sys.argv[2], "content": sys.stdin.read()},
}
if tags:
    data["relationships"] = {"tags": {"data": tags}}
print(json.dumps({"data": data}, ensure_ascii=False))
' "$1" "$TITLE" <<<"$CONTENT"
}

# 解析标签：逗号分隔的名称/slug/ID → JSON 数组（纯数字直接作为 ID）
TAGS_JSON=""
if [ -n "$TAGS_INPUT" ]; then
  TAGS_CACHE="${HOME}/.cache/flarum_idev_tags"
  # 缓存不存在时自动获取
  if [ ! -f "$TAGS_CACHE" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    "$SCRIPT_DIR/fetch_tags.sh" || {
      echo "无法获取标签列表，请先运行 scripts/fetch_tags.sh" >&2
      exit 1
    }
  fi
  TAG_MAP="$(cat "$TAGS_CACHE")"
  IFS=',' read -ra TAG_NAMES <<<"$TAGS_INPUT"
  TAG_IDS=""
  for name in "${TAG_NAMES[@]}"; do
    name="$(echo "$name" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [ -n "$name" ] || continue
    # 纯数字直接作为 ID
    if [[ "$name" =~ ^[0-9]+$ ]]; then
      id="$name"
    else
      id="$(python3 -c '
import json, sys
name = sys.argv[1].lower()
doc = json.load(sys.stdin)
found = None
for t in doc.get("data", []) + doc.get("included", []):
    if t.get("type") != "tags":
        continue
    a = t.get("attributes", {})
    if name in (a.get("name", "").lower(), a.get("slug", "").lower(), t.get("id", "")):
        found = t["id"]
        break
if found is None:
    sys.stderr.write("错误: 未找到标签「" + sys.argv[1] + "」\n")
    sys.stderr.write("可用标签: " + ", ".join(
        t["attributes"]["name"] for t in doc.get("data", []) if t.get("type") == "tags") + "\n")
    sys.exit(1)
print(found)
' "$name" <<<"$TAG_MAP")"
    fi
    TAG_IDS="${TAG_IDS}${TAG_IDS:+,}{\"type\":\"tags\",\"id\":\"$id\"}"
  done
  TAGS_JSON="[$TAG_IDS]"
fi

# 发布
RESPONSE="$(make_json "$TAGS_JSON" | curl -fsS -X POST "$FLARUM_URL/api/discussions" \
  -H "$AUTH" -H "Content-Type: application/json" -d @-)" || {
  echo "发布失败" >&2
  exit 1
}

DISCUSSION_ID="$(echo "$RESPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["id"])')"
echo "发布成功: $FLARUM_URL/d/$DISCUSSION_ID"
