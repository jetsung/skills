---
name: just
description: 使用 just 编写、运行和维护 justfile 命令集。当用户需要创建或修改 justfile、管理配方（recipes）、参数与依赖、配置 shell/环境变量、使用模块与导入、或查询 just CLI/设置/属性/函数时使用本 skill。
license: CC0-1.0
compatibility: 需 just 二进制（>=1.0）；部分特性标注最低版本。POSIX sh 默认，Windows 需 sh（Git for Windows / Cygwin）或配置 shell。
metadata:
  version: "1.0.3"
  upstream: https://github.com/casey/just
  upstream-doc: https://raw.githubusercontent.com/casey/just/refs/heads/master/README.md
  book: https://just.systems/man/en/
---

# Just — 命令运行器

`just` 是 `make` 语法的项目命令运行器，配方存于 `justfile`/`.justfile`，`just <recipe>` 执行。上游：`https://raw.githubusercontent.com/casey/just/refs/heads/master/README.md`（书籍版 `https://just.systems/man/en/`），更新 `python3 skills/just/scripts/update.py`。

## 何时使用

- 提到 `just` / `justfile` / `just --list` / `--choose` / `--fmt`
- 需创建/修改 `justfile`、加参数/依赖、配 shell/env、模块化
- 需查 CLI、设置、属性、函数

## 快速开始

```sh
cargo install just  # 或 brew/apt/dnf/pacman/apk/pixi/conda/npm/pipx/uv
just --version; just --list; just --summary
```

```just
default:  # 首配方为默认，或 [default] / set default-list
  @just --list

# build the project
build target="debug":
  cargo build --{{if target == "release" { "--release" } else { "" } }}

test: build
  cargo test
```

```sh
just; just build release; just test
```

## 核心概念

| 概念 | 形式 |
|------|------|
| 配方 | `name params: deps` + 缩进体，每行 `sh -cu`（`set shell` 可改） |
| 参数 | 必需/可选默认值/可变 `*args`/导出 `$VAR`/`[arg(...)]` 标志 |
| 依赖 | `a: b c` 先跑依赖；`a && b` 串行；`[parallel]` 并行 |
| 变量 | `name := expr` / `export` / `unexport` / `set lazy` |
| 表达式 | `{{expr}}`、字符串/列表/条件/backtick/函数/常量 |
| 属性 | `[private]` `[no-cd]` `[confirm]` `[group]` 等 |
| 设置 | `set shell` / `set dotenv-load` 等全局开关 |
| 模块化 | `import 'file.just'` 文本包含 vs `mod name` 隔离子模块 |

## 书写要点

- 缩进默认 4 空格，`set indentation` 可改，`just --fmt` 统一
- `@` 静默、`-`/`?` 忽略错误（`set guards` 用 `?`）、`#` 注释、`# doc` 显示于 `--list`
- 每行独立 shell：`cd` 跨行无效，用 `&&` 或 `#!/usr/bin/env bash`/`[script]` 单 shell
- `{{expr}}` 于体/依赖/属性求值，`{{{{` 转义 `{{`；`/` 恒为 `/`，`join()` Windows 用 `\`

## CLI 速查

| 场景 | 命令 |
|------|------|
| 列表 | `just --list` / `--unsorted` / `--summary` / `--list <mod>` |
| 查看 | `just --show <r>` / `--dump` / `--dump --dump-format json` |
| 格式 | `just --fmt` / `--fmt --check` |
| 指定 | `just --justfile <p> --working-directory . <r>` / `just dir/r` |
| 变量/参数 | `just var=val <r>` / `--set var val` / `just <r> a b` |
| 交互 | `just --choose`（`$JUST_CHOOSER`/`--chooser`，默认 fzf） |
| 调试 | `just --evaluate` / `-n` dry-run / `--man` / `--completions <sh>` |

## 约束

- 非构建系统，无增量，配方总执行（`[cache]` 除外，需 `set unstable`）
- `import` 文本包含（顺序/深度覆盖特殊），`mod` 隔离（变量/设置不共享，需 `foo::bar`）
- Windows 无 `sh` 时配 `set shell := ["powershell.exe","-c"]`
- `dotenv-load` 向祖先查找 `.env`，`dotenv-path` 仅工作目录，`dotenv-required` 缺报错
- `set lists`/`[cache]` 需 `set unstable`；`--fmt` 不保证向后兼容

## 参考

| 文件 | 何时读 |
|------|--------|
| `references/syntax.md` | 配方/参数/依赖/别名/分组/重复定义 |
| `references/expressions.md` | 变量/插值/类型/函数/常量/sigils |
| `references/execution.md` | shell/script/工作目录/env/dotenv |
| `references/organization.md` | import/mod/fallback/全局/Markdown justfile |
| `references/cli-and-settings.md` | CLI/settings/attributes/缓存/信号 |
| `references/raw.md` | 紧凑 AI 知识库（20K、非逐字、非人类可读） |

## 更新

上游：`https://raw.githubusercontent.com/casey/just/refs/heads/master/README.md`。`references/raw.md` 为手炼紧凑知识库（非逐字去噪）：

```sh
python3 skills/just/scripts/update.py --check  # 抓取上游并校验是否需手炼
python3 skills/just/scripts/update.py          # 抓取失败时仅提示手炼（>40K 时不覆盖）
```

直连→GitHub API→`https://filetas.asfd.cn` 代理（`IS_CHINA=1` 自动）。上游大改时手炼 `raw.md` 并同步 `references/*.md`，后 bump `metadata.version`。
