# AGENTS.md

本文件约束 agent 在本项目（skills 仓库）中的行为。

## Python 脚本规范

- 编写或运行 Python 脚本时，**不得生成 `__pycache__` 目录**：
  - 运行时通过环境变量禁用字节码缓存：`PYTHONDONTWRITEBYTECODE=1`（如 `PYTHONDONTWRITEBYTECODE=1 python3 script.py`）；
  - 或在运行命令中加 `-B` 参数（如 `python3 -B script.py`）；
  - 勿使用 `import` 方式加载 skill 脚本模块（会触发字节码编译生成 `__pycache__`）；
  - 若不慎已生成，需在收尾时清理（`find . -type d -name __pycache__ -exec rm -rf {} +`）。
- 脚本若需校验语法，用 `python3 -c "import ast; ast.parse(open('<file>', encoding='utf-8').read())"`，不要用 `py_compile` / `compileall`（它们必然生成 pyc 缓存文件）。

## SKILL 规范

- 创建新 SKILL 或更新现有 SKILL 时，必须遵循 Agent Skills 官方规范：<https://agentskills.io/>（源码与规范文档：<https://github.com/agentskills/agentskills>）。
- 规范要点：目录必须含 `SKILL.md`（YAML frontmatter + Markdown 正文）；frontmatter 字段约束（`name`/`description` 必填，`name` 为小写字母数字与连字符、与目录名一致且不超 64 字符，`description` 不超 1024 字符）；正文建议不超 500 行，详细内容拆分到 `references/`、`scripts/`、`assets/` 等目录，按需渐进式加载。
- 可用 `uvx --from skills-ref agentskills validate ./skills/<skill-name>` 校验。
- 可用 `uv run --with pyyaml python scripts/validate-frontmatter.py` 做 frontmatter 严格校验（name 与目录名一致、description 长度、metadata 键值类型、规范外字段等）；pyyaml 由 uv 临时注入，无需安装。

## 仓库结构

- `skills/<skill-name>/`：各 skill 目录，含 `SKILL.md`、`docs/`、`examples/`、`references/`、`scripts/`。
- 修改 skill 时同步更新其 `SKILL.md` 中的 `metadata.version`。
