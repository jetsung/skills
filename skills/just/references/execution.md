# 执行 — Shell、环境与工作目录

## Shell

```just
set shell := ["bash", "-cu"]           # 配方行与 backtick
set windows-shell := ["powershell.exe", "-c"]
set script-interpreter := ["sh", "-eu"] # 空 [script] 的解释器
set script-interpreter := ["uv", "run", "--script"]
```

CLI：`just --shell bash --shell-arg -cu`；Windows 无 `sh` 须配 `shell` 或装 Git for Windows/Cygwin。

## Shebang / Script

```just
foo:                 # 单 shell，cd 跨行生效
  #!/usr/bin/env bash
  set -euxo pipefail
  cd bar; pwd

[script]             # 同上，可指定解释器
[script("python3")]
hello:
  print("hello")
set default-script   # 全部默认 script，可 [shell] 覆写
```

提取至临时文件，`set tempdir` 指定目录；`[extension(".py")]` 定扩展。

## 工作目录

- 默认 `justfile` 所在目录；`[no-cd]`/`set no-cd` 保持调用目录；`[working-directory: 'path']`/`set working-directory` 覆盖（相对默认目录解析）
- 切目录同行 `cd bar && cmd` 或用 shebang/script

```just
[no-cd]
commit file:
  git add {{file}}
```

## 环境

```just
export FOO := "bar"
export PATH := "./node_modules/.bin:" + env("PATH")
[env("RUST_BACKTRACE", "1")]
test:
  cargo test
unexport FOO
home := env("HOME")
maybe := env("MAYBE", "default")
```

`set export` 全导出；`export`/`unexport` 入 `cache` key（`[cache(environment=[...])]` 定制）；同域 backtick 不继承导出。

## Dotenv

```just
set dotenv-load                 # 向祖先查找 .env
set dotenv-filename := ".env.local"
set dotenv-path := "/abs/.env" # 仅工作目录
set dotenv-required             # 缺报错
set dotenv-override             # 覆盖已存在
set dotenv-command := 'sops -d .enc.env'  # 或 'mise env'
```

CLI：`--dotenv-path`/`-E`、`--dotenv-filename`/`-F`、`--dotenv-command`（可多次）；子模块继承父 env，可覆盖（>=1.49）。

## 静默与错误

`@` 不回显，`set quiet` 全局，`[no-quiet]` 覆写；`[no-exit-message]`/`set no-exit-message` 不打印失败，`[exit-message]` 强制打印。
