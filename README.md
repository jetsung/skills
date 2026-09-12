# Skills 集合

通用的 AI 编程助手 Skills 集合，适用于支持 Skills 的 AI 工具或自定义 Agent 框架。

## 目录

- [项目简介](#项目简介)
- [Skills 列表](#skills-列表)
  - [git-commit-me](#git-commit-me)
  - [flarum-publish](#flarum-publish)
  - [huawei-deveco-studio-fetch](#huawei-deveco-studio-fetch)
  - [incremental-translate](#incremental-translate)
  - [incremental-translation](#incremental-translation)
  - [model-channel-sync](#model-channel-sync)
  - [update-gh-action-version](#update-gh-action-version)
- [安装](#安装)
- [添加新 Skill](#添加新-skill)
- [许可证](#许可证)

## 项目简介

本项目收录了日常开发中常用的 Agent Skills，每个 Skill 包含一份 `SKILL.md`（描述触发条件与使用规范）以及可选的辅助脚本。AI 助手加载后可根据指令自动执行对应任务。

## Skills 列表

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
- **依赖**：`curl`、`python3`；环境变量 `FLARUM_URL`、`FLARUM_TOKEN`（可选 `FLARUM_USER_ID`）

**特性：**

- 支持两种认证方式：API Key（`Token <key>; userId=<id>`）与 Access Token（`/api/token` 换取）
- 标签按名称或 slug 自动匹配 ID，匹配失败时列出可用标签
- 正文支持 Markdown，通过 JSON:API 规范的 `POST /api/discussions` 创建
- 提供 GitHub 项目 → 中文文章工作流（`docs/github-article.md`）与文章模板（`examples/demo.md`）
- 发布前须经用户确认，发布成功后返回讨论链接

**用法：**

```bash
# 基本用法（无标签）
skills/flarum-publish/scripts/publish.sh "标题" /path/to/article.md

# 带标签（名称或 ID，多个用逗号分隔）
skills/flarum-publish/scripts/publish.sh "标题" /path/to/article.md "问答,教程"

# 正文从 stdin 读入
cat article.md | skills/flarum-publish/scripts/publish.sh "标题" -
```

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

在 `skills/` 目录下创建新的 skill 文件夹，至少包含一个 `SKILL.md` 文件：

```
skills/skill-name/
├── SKILL.md          # 必须：描述 name、description、使用方法
└── scripts/          # 可选：辅助脚本
```

`SKILL.md` 头部需包含 YAML frontmatter：

```yaml
---
name: skill-name
description: 简要描述 skill 的功能与使用场景
---
```

## 许可证

[Apache License 2.0](LICENSE) © 2026 [Jetsung Chan](mailto:i@jetsung.com)

## 仓库镜像

[MyCode](https://git.jetsung.com/jetsung/skills) ● [AtomGit](https://atomgit.com/jetsung/skills) ● [GitHub](https://github.com/jetsung/skills)