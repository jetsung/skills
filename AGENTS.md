# AGENTS.md

本文件约束 agent 在本项目（skills 仓库）中的行为。

## Python 脚本规范

- 编写或运行 Python 脚本时，**不得生成 `__pycache__` 目录**：
  - 运行时通过环境变量禁用字节码缓存：`PYTHONDONTWRITEBYTECODE=1`（如 `PYTHONDONTWRITEBYTECODE=1 python3 script.py`）；
  - 或在运行命令中加 `-B` 参数（如 `python3 -B script.py`）；
  - 勿使用 `import` 方式加载 skill 脚本模块（会触发字节码编译生成 `__pycache__`）；
  - 若不慎已生成，需在收尾时清理（`find . -type d -name __pycache__ -exec rm -rf {} +`）。
- 脚本若需校验语法，用 `python3 -c "import ast; ast.parse(open('<file>', encoding='utf-8').read())"`，不要用 `py_compile` / `compileall`（它们必然生成 pyc 缓存文件）。

## 仓库结构

- `skills/<skill-name>/`：各 skill 目录，含 `SKILL.md`、`docs/`、`examples/`、`references/`、`scripts/`。
- 修改 skill 时同步更新其 `SKILL.md` 中的 `metadata.version`。
