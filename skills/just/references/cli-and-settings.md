# CLI、设置、属性与缓存

## CLI

| 选项 | 作用 |
|------|------|
| `--list` | 按字母列配方；`--unsorted` 保序；`--list-heading`/`--list-prefix` 定制；`--list <mod>` 列子模块（` ` / `::`） |
| `--summary` | 紧凑列表 |
| `--show <r>` | 打印配方定义 |
| `--dump` | 打印格式化 justfile；`--dump-format json` |
| `--fmt` | 原地格式化；`--check` 仅校验；`--indentation` 覆写缩进（默认 4 空格） |
| `--evaluate` | 打印变量求值 |
| `--choose` | chooser 选配方（默认 fzf，`--chooser`/`$JUST_CHOOSER` 覆写） |
| `--completions <sh>` | 生成补全（bash/elvish/fish/nushell/powershell/zsh） |
| `--man` | roff 手册 |
| `--justfile <p>` | 指定文件，`-` 为 stdin，`.md` 提取 ```just 块 |
| `--working-directory <d>` | 覆盖工作目录 |
| `--set <k> <v>` / `k=v` | 覆盖变量，子模块 `foo::bar=v` |
| `--shell <cmd> --shell-arg <a>` | 覆盖 shell |
| `--dotenv-path/-E` `--dotenv-filename/-F` `--dotenv-command` | 覆盖 dotenv（后者可多次） |
| `--timestamp` / `[timestamp]` | 时间戳，`--timestamp-format <fmt>` |
| `--yes` | 自动确认 `[confirm]` |
| `--one` | 限单配方调用 |
| `--jobs <n>` | 并发（配 `[parallel]`） |
| `-n`/`--dry-run` | 只打印不执行 |
| `-g`/`--global-justfile` | 全局 justfile |
| `--clean [r]` | 清 `.justcache`，可指定配方/模块 |
| `--no-cache` / `--changelog` | 跳过缓存 / 打印 changelog |

部分可用环境变量：`JUST_UNSTABLE`/`JUST_CHOOSER`/`JUST_COLOR`/`JUST_INDENTATION`。

## 格式化

```sh
just --fmt; just --fmt --check; just --dump --dump-format json | jq
```

`set indentation` 或 `JUST_INDENTATION` 覆写；格式不保向后兼容。

## 缓存 `[cache]`（unstable，限 script）

```just
set unstable
set lists
[script]
[cache(inputs = "image.png", outputs = "image.jpg", extra = `convert -version`)]
convert:
  convert image.png image.jpg
```

目录 `.justcache`（BLAKE3），key 含 `body`/`environment`/`executor`/`extension`/`extra`/`inputs`/`positional`/`recipe`/`working_directory`；`environment` 默认为 `export`/`unexport` 集，`[cache(environment=['PATH'])]` 定制；`inputs` 哈希内容，`outputs` 仅校验存在；文件锁并发安全；`--no-cache` 跳过。

## 确认 / 时间戳 / 信号

```just
[confirm]  [confirm("Are you sure?")]  [confirm("Deploy to " + env + "?")]
[timestamp]  [timestamp('%H:%M:%S%.3f')]
```

`--yes` 自动确认；失败短路后续；`SIGINT`/`SIGHUP`/`SIGQUIT` 等待子进程，`SIGTERM` 转发，`[continue]`/`[continue("SIGINT")]` 可继续；BSD/macOS `ctrl-t` `SIGINFO` 打印子进程。

## 安装

`cargo install just` / `cargo binstall just` / `brew/apt/dnf/pacman/apk/nix/conda/npm/pipx/uv/arkade/asdf/snap`，预编译 `https://github.com/casey/just/releases`；`export PATH := "./node_modules/.bin:" + env('PATH')` 透 Node bin；GitHub Actions `extractions/setup-just@v3`；补全 `just --completions <sh> > ...`，手册 `just --man | groff -mandoc -Tascii | less`。

## Settings

| 名称 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `allow-duplicate-recipes/variables` | bool | false | 后者覆盖同名 |
| `default-list` | bool | false | 默认列清单 |
| `default-script` | bool | false | 默认 script |
| `dotenv-*` | - | - | `command`/`filename`/`load`/`override`/`path`/`required` |
| `export` | bool | false | 全导出 |
| `fallback` | bool | false | 向父目录回退 |
| `guards` | bool | false | 启用 `?` |
| `ignore-comments` | bool | false | 忽略 `#` 行 |
| `indentation` | string | - | fmt 缩进 |
| `lazy` | bool | false | 惰性求值 |
| `lists` | bool | false | 列表值（unstable） |
| `minimum-version` | string | - | 最低版本 |
| `no-cd` | bool | false | 不切目录 |
| `no-exit-message` | bool | false | 不打印失败 |
| `positional-arguments` | bool | false | 位置参数 |
| `quiet` | bool | false | 静默 |
| `script-interpreter` | [CMD, ARGS…] | ['sh','-eu'] | 空 `[script]` 解释器 |
| `shell` | [CMD, ARGS…] | - | 配方/backtick shell |
| `tempdir` | string | - | 临时目录 |
| `unstable` | bool | false | 启用不稳定 |
| `working-directory` | string | - | 配方/backtick 目录 |

`set NAME` 即 `true`；非布尔可用表达式（无 backtick/函数）。

## Attributes

| 名称 | 作用 | 说明 |
|------|------|------|
| `[arg(..., help/long/max/min/pattern/short/value)]` | recipe | 参数选项/校验 |
| `[cache]` | recipe | 缓存（unstable） |
| `[confirm(PROMPT)]`/`[confirm]` | recipe | 需确认 |
| `[continue(SIGNALS)]` | recipe | 信号后继续 |
| `[default]` | recipe | 默认配方 |
| `[doc(DOC)]` | module/recipe | 文档 |
| `[env(NAME, VALUE)]` | recipe | 单配方 env |
| `[extension(EXT)]` | recipe | 临时扩展名 |
| `[exit-message]`/`[no-exit-message]` | recipe | 打印/不打印失败 |
| `[group(NAME)]` | module/recipe | 分组 |
| `[linux]` `[macos]` `[windows]` `[unix]` `[freebsd]` `[openbsd]` `[netbsd]` `[dragonfly]` `[android]` | any | 平台条件 |
| `[metadata(METADATA)]` | recipe | 元数据（`--dump json`） |
| `[no-cd]` | recipe | 不切目录 |
| `[no-quiet]` | recipe | 覆写 quiet |
| `[parallel]` | recipe | 依赖并行 |
| `[positional-arguments]` | recipe | 位置参数 |
| `[private]` | alias/recipe/var | 私有不列 |
| `[script(COMMAND)]`/`[script]` | recipe | 脚本 |
| `[shell]` | recipe | 强制 shell |
| `[timestamp(FORMAT)]`/`[timestamp]` | recipe | 时间戳 |
| `[working-directory(PATH)]` | recipe | 设工作目录 |

`[no-cd, private]` 或 `[group: 'bar']` 均可。
