#!/usr/bin/env bash
#
# prepare.sh — 增量翻译准备：为源文档目录中每个改动文件生成「翻译输入包」
#
# 痛点：aitr 以整个文件为单位翻译，文件有一处修改就重翻整篇（changelog.md
# 达 100KB+，浪费大量 token）。本 skill 改为「增量」：
#   1. 以 git 基线（默认 HEAD）对比当前工作区源文档目录，找出改动文件；
#   2. 为每个改动文件生成 <WORK_DIR>/<rel>.input.md，内含：
#        - 该文件的英文 diff（仅变更部分，作为翻译增量来源）
#        - 该文件在译文目录的现有译文（作为上下文，避免重翻未改动部分）
#   3. 翻译环节只需把「变更段」翻成目标语言，并就地替换到译文对应位置，
#      产出完整的新译文文件 <WORK_DIR>/<rel>.zh.md；
#   4. apply.sh 把 .zh.md 覆盖回 <ZH_DIR>/<rel>（零对齐风险）。
#
# 通用性：通过环境变量适配任意项目，无需修改脚本。
#   - PROJECT_ROOT 项目根目录（默认：调用时所在目录，或脚本推导）
#   - DOCS_DIR / ZH_DIR 源/译文目录（默认自动探测常见命名）
#   - BASE_REF git 基线（默认 HEAD）
#   - WORK_DIR 中间产物目录（默认 tmp/incr）
#
set -euo pipefail

# 项目根目录：优先用 PROJECT_ROOT，否则取当前工作目录；
# 若脚本位于仓库内的 .agents/skills/...，则回退到脚本上三层目录。
if [[ -n "${PROJECT_ROOT:-}" ]]; then
    ROOT="$PROJECT_ROOT"
elif [[ -d ".git" ]]; then
    ROOT="$(pwd)"
else
    ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
fi
cd "$ROOT"

# 源/译文目录：显式指定优先；否则自动探测常见命名。
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

BASE_REF="${BASE_REF:-HEAD}"
WORK_DIR="${WORK_DIR:-tmp/incr}"

echo "📁 项目根目录: $ROOT"
echo "📂 源目录: $DOCS_DIR | 译文目录: $ZH_DIR | 基线: $BASE_REF"

if [[ ! -d "$DOCS_DIR" ]]; then
    echo "❌ 源目录 $DOCS_DIR 不存在，请用 DOCS_DIR= 指定。" >&2
    exit 1
fi

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"

mapfile -t CHANGED < <(git diff --name-only --diff-filter=AM "$BASE_REF" -- "$DOCS_DIR" 2>/dev/null || true)

if [[ ${#CHANGED[@]} -eq 0 ]]; then
    echo "✅ 没有检测到 $DOCS_DIR 相对 $BASE_REF 的改动。"
    exit 0
fi

echo "🔍 检测到 ${#CHANGED[@]} 个改动文件，生成翻译输入包..."

INDEX="$WORK_DIR/manifest.txt"
: > "$INDEX"

# 支持多语言译文目录探测：若 ZH_DIR 下存在与 rel 同结构文件则使用，否则从零翻译
for f in "${CHANGED[@]}"; do
    case "$f" in
        *.png|*.jpg|*.jpeg|*.gif|*.svg|*.webp) continue ;;
    esac

    rel="${f#"$DOCS_DIR"/}"
    out="$WORK_DIR/${rel}.input.md"
    mkdir -p "$(dirname "$out")"

    {
        echo "<!-- FILE: $rel -->"
        echo "<!-- 以下为英文源文件的 git diff（仅变更部分，请只翻译其中的新增/修改内容） -->"
        echo ""
        echo '```diff'
        git diff --unified=3 "$BASE_REF" -- "$f"
        echo '```'
        echo ""
        echo "<!-- 以下为 $ZH_DIR 中该文件的现有译文，请保留未改动部分、仅更新变更段 -->"
        echo ""
        echo '```markdown'
        if [[ -f "$ZH_DIR/$rel" ]]; then
            cat "$ZH_DIR/$rel"
        else
            echo "<!-- 该文件尚无译文，请根据 diff 从零翻译 -->"
        fi
        echo '```'
    } > "$out"

    bytes=$(wc -c < "$out" | tr -d ' ')
    echo "$rel|$out|$bytes" >> "$INDEX"
    echo "  • $rel  (输入包 ${bytes} 字节)"
done

echo ""
echo "📝 翻译输入包已写入 $WORK_DIR/"
echo "    翻译要求：阅读每个 *.input.md，把 diff 中的变更段翻译为目标语言，"
echo "    输出完整的新译文到 $WORK_DIR/<rel>.zh.md（保留未改动部分原样）。"
echo "    完成后运行：bash <skill>/scripts/apply.sh"
