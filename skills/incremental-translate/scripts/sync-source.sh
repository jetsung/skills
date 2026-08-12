#!/usr/bin/env bash
#
# sync-source.sh — 从上游拉取源码并刷新本地英文源文档目录
#
# 目的：保证「英文源目录」（默认 docs）与上游保持一致，作为后续增量翻译的对比基线。
# 步骤（与项目 deploy.sh / README 约定一致）：
#   1. 把上游仓库（UPSTREAM_URL 指定）拉取/合并到 docsite/（git 仓库）；
#   2. 删除项目当前的英文源目录（docs）；
#   3. 把 docsite 中的文档目录复制为英文源目录（docs）。
#
# 通用性：通过环境变量适配任意项目，无需修改脚本。
#   - PROJECT_ROOT  项目根目录（默认：调用时所在目录）
#   - UPSTREAM_URL  上游仓库地址（必填，如 https://github.com/owner/repo.git）
#   - BRANCH        要跟踪的上游分支（默认 main）
#   - DOCSITE_DIR   docsite 目录（默认 docsite）
#   - DOCS_DIR      英文源目录（默认 docs，自动探测）
#   - UPSTREAM_NAME upstream remote 名（默认 upstream）
#   - COMMIT_FILE   上游 commit 记录文件（默认 commit.txt）
#
set -euo pipefail

# 项目根目录
if [[ -n "${PROJECT_ROOT:-}" ]]; then
    ROOT="$PROJECT_ROOT"
elif [[ -d ".git" ]]; then
    ROOT="$(pwd)"
else
    ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
fi
cd "$ROOT"

UPSTREAM_URL="${UPSTREAM_URL:-}"
BRANCH="${BRANCH:-main}"
DOCSITE_DIR="${DOCSITE_DIR:-docsite}"
UPSTREAM_NAME="${UPSTREAM_NAME:-upstream}"
COMMIT_FILE="${COMMIT_FILE:-commit.txt}"
DOCS_DIR="${DOCS_DIR:-}"

if [[ -z "$UPSTREAM_URL" ]]; then
    echo "❌ 未设置 UPSTREAM_URL，无法拉取上游源码。请用 UPSTREAM_URL= 指定。" >&2
    exit 1
fi

# 自动探测英文源目录名（若未显式指定）
if [[ -z "$DOCS_DIR" ]]; then
    for cand in docs content docs/en en source docs/en-US; do
        [[ -d "$cand" ]] && { DOCS_DIR="$cand"; break; }
    done
fi
DOCS_DIR="${DOCS_DIR:-docs}"

echo "📁 项目根目录: $ROOT"
echo "🌐 上游: $UPSTREAM_URL ($BRANCH) | docsite: $DOCSITE_DIR | 源目录: $DOCS_DIR"

# 1. 初始化 / 更新 docsite git 仓库
[[ -d "$DOCSITE_DIR" ]] || mkdir -p "$DOCSITE_DIR"
pushd "$DOCSITE_DIR" >/dev/null
if [[ ! -d .git ]]; then
    echo "→ 初始化 docsite git 仓库..."
    git init -q
    git remote add "$UPSTREAM_NAME" "$UPSTREAM_URL"
else
    if ! git remote get-url "$UPSTREAM_NAME" >/dev/null 2>&1; then
        echo "→ 添加 $UPSTREAM_NAME remote..."
        git remote add "$UPSTREAM_NAME" "$UPSTREAM_URL"
    else
        current_url=$(git remote get-url "$UPSTREAM_NAME")
        if [[ "$current_url" != "$UPSTREAM_URL" ]]; then
            echo "→ 更新 $UPSTREAM_NAME URL: $current_url → $UPSTREAM_URL"
            git remote set-url "$UPSTREAM_NAME" "$UPSTREAM_URL"
        fi
    fi
fi

git reset --hard -q
git fetch "$UPSTREAM_NAME" "$BRANCH"
git merge "$UPSTREAM_NAME/$BRANCH"

# 记录上游 commit，便于追溯与对比
git rev-parse --short HEAD > "../$COMMIT_FILE"
echo "→ 已更新上游到 commit: $(cat "../$COMMIT_FILE")"
popd >/dev/null

# 2. 删除项目当前的英文源目录
rm -rf "$DOCS_DIR"

# 3. 把 docsite 中的文档目录复制为英文源目录（doc → content → docs 依次探测）
SRC=""
for cand in "$DOCSITE_DIR/doc" "$DOCSITE_DIR/content" "$DOCSITE_DIR/docs"; do
    if [[ -d "$cand" ]]; then
        SRC="$cand"
        break
    fi
done

if [[ -z "$SRC" ]]; then
    echo "❌ $DOCSITE_DIR 下没有 doc / content / docs 目录，无法同步文档。" >&2
    exit 1
fi

cp -r "$SRC" "$DOCS_DIR"
# 移除非 .md/.mdx 的文件
find "$DOCS_DIR" -type f ! \( -name "*.md" -o -name "*.mdx" \) -delete 2>/dev/null || true
echo "✅ 已把 $SRC 同步为 $DOCS_DIR（$(find "$DOCS_DIR" -type f | wc -l) 个文件）"
echo "    接下来请运行 prepare.sh 对比 $DOCS_DIR 相对上次提交的改动。"
