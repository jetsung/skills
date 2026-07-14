---
name: git-commit
description: Generates standardized git commit messages following the Conventional Commits format with Chinese descriptions. Use when committing changes, creating git commits, or writing commit messages.
metadata:
  version: "1.2.0"
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
4. **Write the description**:
   - 使用**简体中文**
   - 简洁描述变更内容
   - 不加句号
   - 多个功能修改时，使用列表形式（每项以 `- ` 开头，各占一行），而不是一句话总结
5. **Execute**: `git commit -m "<type>(<scope>): <description>"`
6. **Verify**: 运行 `git status` 确认提交成功

## Constraints

- **禁止使用 `Co-Authored-By`**: 提交信息中不得添加任何 `Co-Authored-By` 尾行（例如 `Co-Authored-By: Claude <noreply@anthropic.com>`）。始终使用简单的 `git commit -m` 形式，不包含任何尾部元数据行。
- **禁止推送到远程仓库**: 只执行本地 `git commit`，不得执行 `git push` 或任何推送到远程仓库的操作。

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
