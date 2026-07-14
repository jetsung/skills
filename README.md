# Skills 集合

通用的 AI 编程助手 Skills 集合，适用于支持 Skills 的 AI 工具或自定义 Agent 框架。

## 目录

- [项目简介](#项目简介)
- [Skills 列表](#skills-列表)
  - [git-commit](#git-commit)
  - [update-gh-action-version](#update-gh-action-version)
- [安装](#安装)
- [添加新 Skill](#添加新-skill)
- [许可证](#许可证)

## 项目简介

本项目收录了日常开发中常用的 Agent Skills，每个 Skill 包含一份 `SKILL.md`（描述触发条件与使用规范）以及可选的辅助脚本。AI 助手加载后可根据指令自动执行对应任务。

## Skills 列表

### git-commit

> 生成符合 [Conventional Commits](https://www.conventionalcommits.org/) 规范的 git 提交信息，描述部分使用简体中文。

- **触发场景**：提交代码、生成 commit message
- **路径**：`skills/git-commit/`

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

### update-gh-action-version

> 自动检测并更新 GitHub Actions 工作流文件中使用的 Action 版本至最新主版本。

- **触发场景**：需要升级 workflow 中的 action 版本
- **路径**：`skills/update-gh-action-version/`
- **依赖**：`curl`、`sed`、GitHub API 访问

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

