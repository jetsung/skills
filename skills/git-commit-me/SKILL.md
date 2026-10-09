---
name: git-commit-me
description: Generates standardized git commit messages following the Conventional Commits format with Chinese descriptions. Use when committing changes, creating git commits, or writing commit messages.
metadata:
  version: "1.3.0"
---

# Git Commit Message Generation

## Instructions

When asked to commit changes, follow these steps:

1. **Analyze staged changes**: Run `git diff --staged` to identify what needs to be committed. If nothing is staged, ask the user to stage files first — this skill only commits already-staged content.
2. **Determine the type**:
   - `feat`: 新功能
   - `fix`: 修复 bug
   - `docs`: 仅文档变更
   - `style`: 不影响代码含义的格式变更
   - `refactor`: 既非修复 bug 也非新增功能的代码变更
   - `perf`: 性能优化
   - `test`: 添加或修正测试
   - `build`: 影响构建系统或外部依赖的变更
   - `ci`: CI 配置文件和脚本变更
   - `chore`: 其他不影响 src 或 test 的变更
   - `revert`: 回退之前的提交
3. **Determine the scope** (可选): 具体模块、目录或组件名称（如 `utils`、`api`、`readme`）
4. **Determine the granularity**（提交粒度，重要）:
   - **默认只创建一个提交**：即使是大量文件或大 diff，只要属于同一目的（同一功能、同一修复、同一次重构），就合并为一个提交，用多行列表逐条描述各项变更。
   - **不要按文件拆分**：文件数量多不是拆分提交的理由；不要为每个文件单独建提交。
   - 仅当变更包含**真正独立的目的**（例如：一个功能 + 一处不相关的紧急修复；代码变更 + 无关联的文档变更）时才拆分，且通常不超过 2~3 个提交。
   - 拆分前先问：这些提交是否需要被单独 revert 或单独回溯？如果不需要，就合并为一个提交。
5. **Write the description**:
   - 使用**简体中文**
   - 简洁描述变更内容
   - 不加句号
   - 多个功能修改时，使用列表形式（每项以 `- ` 开头，各占一行），而不是一句话总结
6. **Execute**: `git commit -m "<type>(<scope>): <description>"`
7. **Verify**: 运行 `git status` 确认提交成功

## Constraints

- **禁止使用 `Co-Authored-By`**: 提交信息中不得添加任何 `Co-Authored-By` 尾行（例如 `Co-Authored-By: Claude <noreply@anthropic.com>`）。始终使用简单的 `git commit -m` 形式，不包含任何尾部元数据行。
- **禁止推送到远程仓库**: 只执行本地 `git commit`，不得执行 `git push` 或任何推送到远程仓库的操作。
- **禁止过细拆分**: 每个提交承载一个完整目的；一个提交应自成一个可 revert 的单元。

## Examples

- `feat(adminer): 添加 compose 配置文件`
- `fix(utils): 修复日期格式化错误`
- `docs(README): 更新项目说明`
- `chore(deps): 升级依赖包`
- 多行列表示例：
  ```
  feat(utils): 添加常用工具函数
  - 添加日期格式化函数
  - 添加字符串截断函数
  - 添加深拷贝函数
  ```
