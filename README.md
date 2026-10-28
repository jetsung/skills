# Skills 集合

通用的 AI 编程助手 Skills 集合，适用于支持 Skills 的 AI 工具或自定义 Agent 框架。

## 目录
- [项目简介](#项目简介)
- [Skills 列表](#skills-列表)
  - [atuin](#atuin)
  - [flarum-publish](#flarum-publish)
  - [git-commit-me](#git-commit-me)
  - [google-rust-styleguide](#google-rust-styleguide)
  - [huawei-deveco-studio-fetch](#huawei-deveco-studio-fetch)
  - [incremental-translate](#incremental-translate)
  - [incremental-translation](#incremental-translation)
  - [just](#just)
  - [model-channel-sync](#model-channel-sync)
  - [navi](#navi)
  - [update-gh-action-version](#update-gh-action-version)
- [安装](#安装)
- [添加新 Skill](#添加新-skill)
- [许可证](#许可证)

## 项目简介

本项目收录了日常开发中常用的 Agent Skills，每个 Skill 包含一份 `SKILL.md`（描述触发条件与使用规范）以及可选的辅助脚本。AI 助手加载后可根据指令自动执行对应任务。

## Skills 列表

### atuin

> 安装、配置、使用与排障 Atuin —— 用 SQLite 数据库替换 shell 内置历史的工具（记录 cwd、退出码、耗时、主机与会话），支持端到端加密同步与常驻 daemon。

- **触发场景**：安装 Atuin、配置 shell 插件、注册/登录/同步账号、导入旧历史、搜索/过滤/删除历史、调整 `config.toml` 或快捷键、排除敏感命令、安装 AI agent hooks（claude-code / codex / opencode / pi）、编写 `.atuin/skills`、自建同步服务、运行 `atuin doctor`
- **路径**：`skills/atuin/`
- **依赖**：任意 POSIX shell；文档基于 Atuin >= 18.18；`cargo`/`gh` 仅自建服务时需要

**特性：**

- 覆盖完整使用路径：安装 → shell 集成 → 账号与同步 → 历史管理 → 配置调优
- 按需加载 `references/`（cli / config / daemon / agent-hooks / excluding / mcp / self-hosting）
- 含 AI agent hooks 与 `.atuin/skills` 集成指引

**用法：**

```bash
# 安装后挂到 shell（zsh 示例）
eval "$(atuin init zsh)"

# 搜索历史 / 同步
atuin search "关键词"
atuin sync

# 体检排障
atuin doctor
```

---

### git-commit-me

> 生成符合 [Conventional Commits](https://www.conventionalcommits.org/) 规范的 git 提交信息，描述部分使用简体中文。

- **触发场景**：提交代码、生成 commit message
- **路径**：`skills/git-commit-me/`

**特性：**

- 自动分析暂存区变更（`git diff --staged`）
- 根据变更类型选择合适的 commit type（`feat`、`fix`、`docs`、`refactor` 等）
- 多个功能修改时自动使用列表形式描述
- 禁止添加 `Co-Authored-By` 尾行
- 仅执行本地 commit，不会推送到远程仓库

**示例输出：**

```
feat(utils): 添加常用工具函数
- 添加日期格式化函数
- 添加字符串截断函数
- 添加深拷贝函数
```

---

### flarum-publish

> 发布文章（主题）到 Flarum 论坛：通过 REST API 创建讨论，支持按名称匹配标签；也可将 GitHub 项目链接整理为中文论坛文章后发布。

- **触发场景**：发布/投稿文章到 Flarum 论坛、同步内容到论坛、把 GitHub 项目整理成论坛文章
- **路径**：`skills/flarum-publish/`
- **依赖**：`uv`（`uv run --script` 自动装 `requests`）；图片压缩可选 `oxipng`/`rimage`/`resvg`；环境变量 `FLARUM_URL`、`FLARUM_TOKEN`（可选 `FLARUM_USER_ID`）

**特性：**

- 脚本内联声明依赖（PEP 723），`uv run --script` 直接运行，无需手动建 venv
- 支持两种认证方式：API Key（`Token <key>; userId=<id>`）与 Access Token（`/api/token` 换取）
- 标签按名称或 slug 自动匹配 ID，二级标签自动补全父级，匹配失败时列出可用标签
- 正文支持 Markdown，通过 JSON:API 规范的 `POST /api/discussions` 创建
- 提供 GitHub 项目 → 中文文章工作流（`docs/github-article.md`）与文章模板（`examples/demo.md`）
- 发布前须经用户确认，发布成功后返回讨论链接

**用法：**

```bash
# 基本用法（无标签）
uv run --script skills/flarum-publish/scripts/publish.py "标题" /path/to/article.md

# 带标签（名称或 ID，多个用逗号分隔）
uv run --script skills/flarum-publish/scripts/publish.py "标题" /path/to/article.md "55,57,21"

# 正文从 stdin 读入
cat article.md | uv run --script skills/flarum-publish/scripts/publish.py "标题" -
```

**一句话安装提示词：**

```
从 https://github.com/jetsung/skills 安装 flarum-publish SKILL（skills/flarum-publish），并按 references/image-compression.md 用 fx4.cn 短链安装图片压缩工具 oxipng、rimage、resvg。
```

---

### google-rust-styleguide

> 按 Google Rust 风格指南（[rustguide](https://google.github.io/styleguide/rustguide.html)）编写、修改与评审 Rust 代码：覆盖代码组织、导入规则、所有权与 API 设计、类型与 trait、命名、文档注释、unsafe 与实现细节。

- **触发场景**：编写/修改/重构 Rust 代码、评审 Rust PR/diff、设计 Rust API、配置 rustfmt/clippy、讨论 Rust 风格分歧
- **路径**：`skills/google-rust-styleguide/`
- **依赖**：无外部依赖（纯指令型 skill）

**特性：**

- `SKILL.md` 提供核心原则、规则速览与评审对照清单
- 六个主题参考文件按需加载：code-organization / ownership-and-apis / types-and-traits / naming-and-docs / language-features / implementation-concerns
- 区分库代码与应用代码的 API 设计规则强度；含 rustfmt 推荐配置与 `#[rustfmt::skip]` 使用边界

---

### huawei-deveco-studio-fetch

> 提取华为 DevEco Studio / Command Line Tools 的下载地址与 SHA-256 校验值。不真正下载文件，仅读取响应头 `x-amz-content-sha256`。

- **触发场景**：从华为开发者联盟下载中心获取 DevEco Studio / Command Line Tools 的签名下载链接与校验和
- **路径**：`skills/huawei-deveco-studio-fetch/`
- **依赖**：`chrome-devtools` MCP（浏览器需以真正 headless 模式运行）

**特性：**

- 按「最新版本」页卡片顺序提取 DevEco Studio Release/Beta（Mac x86）与 Command Line Tools Release/Beta（Linux x86）的下载地址与 SHA-256
- 通过触发下载请求读取响应头获取哈希，文件不落盘
- 结果回显并保存至 `/tmp/deveco.txt`

---

### incremental-translate

> 对中文文档项目做「段落级增量翻译」：只提取源文档相对上次提交的变更段落交给内置 LLM 翻译，未改动部分复用已有译文，并自动清理已删除文档对应的中文译文。

- **触发场景**：上游文档小幅更新（尤其 changelog 等超大文件）时避免整篇重翻、节省 token
- **路径**：`skills/incremental-translate/`
- **依赖**：内置 LLM（本工具）、git；不依赖第三方翻译工具

**特性：**

- 通过环境变量（`PROJECT_ROOT`、`DOCS_DIR`、`ZH_DIR`、`BASE_REF`）适配任意项目，零配置自动探测常见目录
- 提供 `sync-source.sh` / `prepare.sh` / `apply.sh` 三阶段工作流
- 自动清理上游已删除文档对应的中文译文

---

### incremental-translation

> 通用中文文档项目的增量更新与 AI 翻译工作流：拉取上游最新文档、对比改动、生成待翻译列表并执行增量翻译。

- **触发场景**：基于 `deploy.sh` 约定的文档项目需要整体增量更新与翻译
- **路径**：`skills/incremental-translation/`
- **依赖**：项目根目录的 `deploy.sh`（约定 `UPSTREAM_URL`、`BRANCH` 等环境变量）、`aitr` CLI 工具

**特性：**

- 不绑定特定项目，通过环境变量适配任意文档仓库，同一 skill 可复用于多个项目
- 一键完成「拉取上游 → 清理已删除文档 → 识别新增/修改文件 → 增量翻译」
- 翻译环节可配合 `incremental-translate` skill 进一步节省 token

---

### model-channel-sync

> 管理 AI 模型渠道配置：①提取真正可用的免费/零价模型；②以 pi 等平台配置为基准，将渠道、模型、APIKEY 同步到多个 agent 工具的配置文件。

- **触发场景**：查询渠道免费模型、测试模型可用性、把模型/密钥同步到 pi、omp、opencode、dsh、zcode、qoder-cn 等工具
- **路径**：`skills/model-channel-sync/`
- **依赖**：`curl`、`python3`、目标渠道的 `baseUrl` 与 `apiKey`

**特性：**

- 支持 openrouter、kilo、opencode、newapi、nvidia、atomgit 等所有 OpenAI 兼容渠道
- 「抓取 → 筛选（按价格=0 / free 标签 / 关键词）→ 连通性实测 → 剔除不可用」完整闭环
- 按各工具配置文件结构（pi / omp / opencode / dsh / zcode / qoder-cn）分别匹配渠道、合并模型、更新密钥并写回校验

---

### navi

> 创建和管理 navi 交互式 cheatsheet（.cheat/.cheat.md）：支持变量 `<var>`、动态候选 `$ var:`、依赖继承 `@`、多行 snippet 与 fzf 选项定制。

- **触发场景**：创建、修改、验证、分享 cheatsheet；为 CLI/工具生成可交互命令模板
- **路径**：`skills/navi/`
- **依赖**：`python3`（校验）；`navi` + `fzf`/`skim`（预览/交互）

**特性：**

- 完整 cheatsheet 语法（`%` tags / `#` 描述 / `$` 变量 / `@` 继承 / `;` 元注释 / Markdown 代码块）与 `src/parser.rs` 解析规则对齐
- `scripts/validate.py` 校验：tags/描述/命令完整性、`<var>` 与 `$` 一致性（含 `@` 继承）、`---` 选项合法性、续行与 Markdown 块闭合、重复去重
- 按需加载 `references/`（syntax / variables / paths / examples）与 `assets/templates/` 模板

**用法：**

```bash
# 从模板新建
cp skills/navi/assets/templates/basic.cheat /tmp/my.cheat
# 编辑后校验
python3 skills/navi/scripts/validate.py /tmp/my.cheat
# 预览（需 navi）
navi --path "/tmp" --query "关键词"
```

### just

> `just` 命令运行器：基于 `justfile` 管理项目级配方（recipes），支持参数、依赖、导入/模块、环境与 dotenv、shell/shebang/script 及完整 CLI。

- **触发场景**：编写或执行 `justfile`、管理配方与依赖、配置 shell/环境变量、使用模块与导入、查询 `just` CLI/设置/属性/函数
- **路径**：`skills/just/`
- **依赖**：`just` 二进制（`cargo install just` 等）；`python3`（仅更新文档时）

**特性：**

- `SKILL.md` 精简指令 + 按需加载 `references/`（syntax / expressions / execution / organization / cli-and-settings）
- 去噪后的上游快照 `references/raw.md`（保留更新 URL），配合 `scripts/update.py` 一键刷新（直连 → GitHub API → `https://filetas.asfd.cn` 代理，`IS_CHINA=1` 自动走代理）
- 覆盖配方、参数、依赖、属性、设置、函数、缓存、信号、格式化等完整能力

**用法：**

```bash
# 列出/执行配方
just --list
just <recipe> [args]

# 格式化
just --fmt

# 更新上游文档快照
python3 skills/just/scripts/update.py --check
python3 skills/just/scripts/update.py
```

---

### update-gh-action-version

> 自动检测并更新 GitHub Actions 工作流文件中使用的 Action 版本至最新主版本。

- **触发场景**：需要升级 workflow 中的 action 版本
- **路径**：`skills/update-gh-action-version/`
- **依赖**：`curl`、`sed`、GitHub API 访问（可设置 `GITHUB_TOKEN` 提高速率限制）

**用法：**

```bash
# 更新 .github/workflows 下所有 Action 版本
skills/update-gh-action-version/scripts/update_action.sh

# 更新指定目录下的所有 Action 版本
skills/update-gh-action-version/scripts/update_action.sh .test/test/

# 仅更新指定 Action（如 actions/checkout）的版本
skills/update-gh-action-version/scripts/update_action.sh .test/test/ actions/checkout
```

**工作原理：**

1. 扫描目标目录下的 `.yml` / `.yaml` 文件
2. 通过 GitHub API 查询每个 Action 的最新 release tag
3. 提取主版本号（如 `v4.1.0` → `v4`）
4. 使用 `sed` 批量替换工作流文件中的版本引用

---

## 安装

```bash
git clone https://github.com/jetsung/skills.git
```

将本仓库放置在 AI 助手可识别的 skills 目录中即可。具体路径请参考对应 AI 工具的 Skills 文档。

## 添加新 Skill

遵循 [Agent Skills](https://agentskills.io/) 官方规范（详见 [AGENTS.md](AGENTS.md) 的「SKILL 规范」一节），在 `skills/` 目录下创建新的 skill 文件夹：

```
skills/skill-name/
├── SKILL.md          # 必须：YAML frontmatter + Markdown 正文
├── references/       # 可选：按需加载的详细文档
├── scripts/          # 可选：辅助脚本
└── assets/           # 可选：模板与静态资源
```

`SKILL.md` 头部需包含 YAML frontmatter：

```yaml
---
name: skill-name        # 小写字母/数字/连字符，与目录名一致，≤64 字符
description: 简要描述 skill 的功能与使用场景（≤1024 字符）
metadata:
  version: "1.0.0"
---
```

正文建议不超过 500 行，详细内容拆分到 `references/` 等目录按需加载。

提交前运行校验：

```bash
# 官方规范校验（单个 skill）
uvx --from skills-ref agentskills validate ./skills/skill-name

# frontmatter 严格校验（全部 skill）
uv run --with pyyaml python scripts/validate-frontmatter.py
```

## 许可证

[Apache License 2.0](LICENSE) © 2026 [Jetsung Chan](mailto:i@jetsung.com)

## 仓库镜像

[MyCode](https://git.jetsung.com/jetsung/skills) ● [AtomGit](https://atomgit.com/jetsung/skills) ● [GitHub](https://github.com/jetsung/skills)
