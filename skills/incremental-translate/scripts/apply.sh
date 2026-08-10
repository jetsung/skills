#!/usr/bin/env bash
#
# apply.sh — 把翻译产出的完整译文覆盖回译文目录
#
# 前置：prepare.sh 生成 <WORK_DIR>/<rel>.input.md；翻译环节产出
#       <WORK_DIR>/<rel>.zh.md（完整新译文）。
# 本脚本把每个 .zh.md 覆盖回 <ZH_DIR>/<rel>，并在覆盖前做基本校验：
#   - .zh.md 必须存在且非空；
#   - 必须保留 YAML frontmatter（以 --- 开头）或与原译文结构一致。
#
# 通用性：通过 PROJECT_ROOT / DOCS_DIR / ZH_DIR / WORK_DIR 适配任意项目。
#
set -euo pipefail

if [[ -n "${PROJECT_ROOT:-}" ]]; then
    ROOT="$PROJECT_ROOT"
elif [[ -d ".git" ]]; then
    ROOT="$(pwd)"
else
    ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
fi
cd "$ROOT"

detect_dirs() {
    local cand
    for cand in docs docs/en content en source docs/en-US; do
        [[ -d "$cand" ]] && { DOCS_DIR="$cand"; break; }
    done
    for cand in docs_zh docs/zh content_zh zh translated docs/zh-CN; do
        [[ -d "$cand" ]] && { ZH_DIR="$cand"; break; }
    done
}
DOCS_DIR="${DOCS_DIR:-}"
ZH_DIR="${ZH_DIR:-}"
detect_dirs
DOCS_DIR="${DOCS_DIR:-docs}"
ZH_DIR="${ZH_DIR:-docs_zh}"

WORK_DIR="${WORK_DIR:-tmp/incr}"

INDEX="$WORK_DIR/manifest.txt"
[[ -f "$INDEX" ]] || { echo "❌ 未找到 $INDEX，请先运行 prepare.sh"; exit 1; }

ok=0; skip=0
while IFS='|' read -r rel input_out bytes; do
    [[ -n "$rel" ]] || continue
    zh_file="$WORK_DIR/${rel}.zh.md"
    dst="$ZH_DIR/$rel"

    if [[ ! -s "$zh_file" ]]; then
        echo "⚠️  跳过 $rel：译文 $zh_file 不存在或为空"
        skip=$((skip+1)); continue
    fi

    # 基本校验：译文应以 --- 开头（保留 frontmatter）或至少非空
    first="$(head -1 "$zh_file")"
    if [[ "$first" != "---" && "$first" != "<!-- FILE:"* ]]; then
        echo "⚠️  跳过 $rel：译文首行不是 frontmatter（检查是否被包裹在代码块中）"
        skip=$((skip+1)); continue
    fi

    mkdir -p "$(dirname "$dst")"
    cp "$zh_file" "$dst"
    echo "✅ 已更新 $rel"
    ok=$((ok+1))
done < "$INDEX"

echo ""
echo "🎉 回填完成：$ok 个文件已更新，$skip 个跳过。"
echo "    请运行 git diff $ZH_DIR/ 检查译文，确认无误后提交。"
