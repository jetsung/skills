---
name: incremental-translate
description: 对中文文档项目做「段落级增量翻译」，先从上游同步英文源文档，再只提取源目录相对上次提交的变更段落交给内置 LLM（本工具）翻译，未改动部分复用已有译文，并自动清理上游已删除文档对应的中文译文，避免整文件重翻浪费 token。当源文档目录相对上次提交只改动了少量内容（尤其 changelog 等超大文件）时使用。通用 skill，不绑定特定项目。
---

# 增量翻译（Incremental Translate）

> 本 skill 为**通用** skill：通过环境变量指定「英文源目录」「中文译文目录」「git 基线」
> 即可用于任何文档项目，不绑定特定上游仓库或构建工具。
>
> 本 skill **只使用内置 LLM（本工具）直接翻译**，不依赖任何第三方翻译工具。

## 背景与痛点

传统做法以**整个文件**为最小翻译单元：只要源文档目录中某个文件有一处改动，就会把
整篇重新翻译。像 `changelog.md`、`configuration.md` 等文件体积较大，每次上游小改
都要重翻整篇，极其浪费 token 与时间。

本 skill 改为**增量**思路：只提取源文档目录相对 git 基线（`HEAD`，即上次提交的版本）
的**变更段落**交给内置 LLM 翻译，未改动部分直接复用译文目录中已有的译文，从而把
token 消耗从「整篇」降到「改动量」。

## 关键概念（可配置）

| 概念 | 环境变量 | 默认值 | 说明 |
|------|----------|--------|------|
| 项目根目录 | `PROJECT_ROOT` | 当前目录 / 脚本推导 | 仓库根，脚本在其下查找文档目录 |
| 英文源目录 | `DOCS_DIR` | 自动探测 | 待翻译的英文原文所在目录 |
| 中文译文目录 | `ZH_DIR` | 自动探测 | 已翻译/将写入的中文译文目录 |
| git 基线 | `BASE_REF` | `HEAD` | 对比起点（上次提交的版本） |
| 中间产物目录 | `WORK_DIR` | `tmp/incr` | 翻译输入包/产出存放处 |

### 零配置自动探测

不设置 `DOCS_DIR` / `ZH_DIR` 时，脚本按以下顺序自动探测存在的目录：

- 源目录：`docs` → `docs/en` → `content` → `en` → `source` → `docs/en-US`
- 译文目录：`docs_zh` → `docs/zh` → `content_zh` → `zh` → `translated` → `docs/zh-CN`

> 不同项目目录命名不同（如 `docs`/`docs_zh`、`content`/`content_zh`、`en`/`zh`），
> 既能零配置自动识别，也可在调用脚本前显式设置环境变量覆盖。

## 工作流

本 skill 提供三个脚本（位于 `scripts/`），均通过环境变量适配不同项目：

- **`sync-source.sh`** — 从上游拉取源码并刷新英文源目录（可选，首次或上游有更新时执行）
- **`prepare.sh`** — 提取变更，生成翻译输入包，并列出被删除的文档
- **`apply.sh`** — 回填译文，并清理被删除文档对应的中文译文

### 0. 同步上游源码（可选但推荐）

当上游仓库有更新时，先用本脚本把最新源码拉取到 `docsite/`，再删除项目当前的英文源目录
（`docs`），并把上游文档复制为 `docs`。**这保证后续 diff 对比的是上游最新文档。**

```bash
# 方式 A：零配置（脚本自动在 docsite/ 拉取、更新 docs/）
UPSTREAM_URL=https://github.com/owner/repo.git \
  bash <skill>/scripts/sync-source.sh

# 方式 B：指定分支 / 项目根 / docsite 目录
PROJECT_ROOT=/path/to/other-project UPSTREAM_URL=... BRANCH=develop \
  bash <skill>/scripts/sync-source.sh
```

- 在 `docsite/` 初始化或更新 git 仓库，拉取合并 `$BRANCH`（默认 `main`）
- 把上游 commit 写入 `commit.txt`，便于追溯与对比
- 删除项目当前 `$DOCS_DIR`（默认 `docs`），再把 `docsite/doc`（或 `content`/`docs`）
  复制为 `$DOCS_DIR`
- 同步后会**自动清理** `$DOCS_DIR` 中的非 `.md`/`.mdx` 文件，确保只有文档文件进入翻译流程

> 若 `docsite/` 已是最新、源目录无需刷新，可跳过本步直接进入 prepare。

### 1. 准备：提取变更，生成翻译输入包

```bash
# 方式 A：零配置（脚本自动探测 docs/ + docs_zh/ 等常见目录）
bash <skill>/scripts/prepare.sh

# 方式 B：显式指定（适用于任意命名）
DOCS_DIR=content ZH_DIR=content_zh BASE_REF=HEAD \
  bash <skill>/scripts/prepare.sh

# 方式 C：翻译仓库外的项目
PROJECT_ROOT=/path/to/other-project DOCS_DIR=docs ZH_DIR=docs_zh \
  bash <skill>/scripts/prepare.sh
```

- **预处理**：先清理 `$ZH_DIR` 中的非 `.md`/`.mdx` 文件，确保只处理文档
- 对比 `git diff $BASE_REF -- $DOCS_DIR`，找出新增/修改的 `.md` 文件
  （供 apply.sh 清理对应的中文译文）
- 为每个改动文件生成 `$WORK_DIR/<相对路径>.input.md`，内含：
  1. 该文件的英文 **git diff**（仅变更部分）
  2. 译文目录中该文件的**现有译文**（作为上下文，避免重翻未改动段）
- 清单写入 `$WORK_DIR/manifest.txt`

### 2. 翻译（由本工具 / 内置 LLM 执行）

使用内置 LLM（本工具）直接翻译。阅读每个 `$WORK_DIR/<rel>.input.md`：
- 看 `diff` 部分，识别**新增/修改**的英文段落
- 把这些段落翻译为目标语言（默认简体中文），**保持原译文未改动部分原样**
- 输出**完整的新译文**到 `$WORK_DIR/<rel>.zh.md`

翻译要求（由本工具作为翻译模型遵循）：
- 保留 Markdown 结构、frontmatter、短代码、代码块原样，不翻译代码/命令
- 保留未改动部分的原译文，仅更新 diff 中出现的变更段
- 译文必须是**完整文件**，首行保留 `---`（YAML frontmatter）或 `<!-- FILE:`，
  不要包裹在 ```markdown 代码块中

> ⚠️ **标题锚点陷阱**：多数文档站点标题锚点由标题文本自动生成。
> 若把被链接指向的标题翻译成中文，锚点会变成目标语言 slug，导致所有指向它的
> `#anchor` 链接失效、构建失败。**凡是文档中任何 `#anchor` 链接所指向的标题，
> 必须保留原文原名**（可括号附译文）；普通未被引用的标题可正常翻译。

### 3. 回填：覆盖到译文目录

```bash
# 与 prepare.sh 使用相同的目录配置即可；PROJECT_ROOT 同理可指定
bash <skill>/scripts/apply.sh
```

- 把每个 `$WORK_DIR/<rel>.zh.md` 覆盖回 `$ZH_DIR/<rel>`
- 覆盖前校验：文件非空、首行为 `---` 或 `<!-- FILE:`
- **回填后清理**：再次清理 `$ZH_DIR` 中的非 `.md`/`.mdx` 文件，确保构建安全
- **清理删除**：读取 `$WORK_DIR/deleted.txt`，删除 `$ZH_DIR/` 中对应的中文译文
  （即英文文档已在上游删除时，同步移除其中文文档）
- 完成后用 `git diff $ZH_DIR/` 人工核对

## 参数（环境变量）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PROJECT_ROOT` | 当前目录 / 脚本推导 | 项目（仓库）根目录 |
| `DOCS_DIR` | 自动探测（默认 `docs`） | 英文源目录 |
| `ZH_DIR` | 自动探测（默认 `docs_zh`） | 中文译文目录 |
| `BASE_REF` | `HEAD` | git 基线（对比起点） |
| `WORK_DIR` | `tmp/incr` | 中间产物目录 |

`sync-source.sh` 专用参数：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `UPSTREAM_URL` | —（必填） | 上游仓库地址（如 `https://github.com/owner/repo.git`） |
| `BRANCH` | `main` | 要跟踪的上游分支 |
| `DOCSITE_DIR` | `docsite` | docsite（上游 clone）目录 |
| `UPSTREAM_NAME` | `upstream` | docsite 中 upstream remote 名 |
| `COMMIT_FILE` | `commit.txt` | 上游 commit 记录文件 |

示例（对比某个特定上游 commit）：

```bash
BASE_REF=8385554 bash <skill>/scripts/prepare.sh
```

示例（翻译另一个项目）：

```bash
PROJECT_ROOT=/path/to/other-project BASE_REF=HEAD \
  bash <skill>/scripts/prepare.sh
```

## 适用场景

- 上游文档更新后，源目录只有少量文件/段落改动
- 需要把英文源的新增、修改内容同步到译文目录
- 上游删除了某些英文文档，需要同步清理对应的中文文档
- 特别适合 `changelog.md`、`configuration.md` 等大体量文件的小幅更新

> 若是**首次全量翻译**或文件整体大改，可跳过增量流程，直接用本工具按整篇翻译。

## 注意事项

- 建议把 `$WORK_DIR`（如 `tmp/`）加入 `.gitignore`，中间产物不会污染仓库
- **先同步后对比**：每次同步上游前，先 `git add` + 提交当前译文，再运行
  `sync-source.sh` 刷新 `docs`，这样 `git diff HEAD` 对比的才是真实的上游变更
- `sync-source.sh` 会**删除并重建** `$DOCS_DIR`，请确认没有未提交的源文档改动
- 翻译时**务必保留未改动部分**，否则等于整篇重翻
- 被删除英文文档对应的中文译文会由 `apply.sh` 自动清理，无需手动删除
- 大文件建议让内置 LLM「只输出变更段的新译文、其余照搬」，以进一步省 token
- 回填后务必 `git diff $ZH_DIR/` 核对，确认格式未被破坏再提交
- **回填前建议做锚点校验**：扫描译文目录中所有 `#anchor` 链接，确认每个锚点都能在
  目标译文里找到对应的原文标题；凡是被引用的标题必须保留原文，否则构建会失败。可参考命令：
  ```bash
  grep -rhoE '(href=|]\()#[a-zA-Z][a-zA-Z0-9_-]*' "$ZH_DIR" | sed -E 's/(href=|]\()#//' | sort -u
  ```
