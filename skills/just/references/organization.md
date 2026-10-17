# 组织 — 导入、模块与调用

## import（文本包含）

```just
import 'foo/bar.just'
import? 'optional.just'         # 可选
import '~/shared/common.just'   # ~/ -> HOME
```

相对 justfile 解析，递归，重复导入不报错（>=1.37）；`allow-duplicate-*` 时后者覆盖，先导入者同深度优先（详见 `raw.md`）。

```just
import? 'foo.just'
fetch:
  curl https://raw.githubusercontent.com/.../foo.just > foo.just
```

## mod（隔离子模块）

```just
mod bar                         # bar.just / bar/mod.just / bar/justfile / bar/.justfile
mod foo 'PATH'                  # 指定文件或目录
mod? foo                        # 可选
mod? foo 'bar.just'
mod? foo 'baz.just'             # 多可选同名仅一存在即不冲突
```

- 查找：`foo.just` → `foo/mod.just` → `foo/justfile` → `foo/.justfile`（后二大小写不敏感）
- 隔离：变量/别名/设置不共享，依赖 `foo::bar` 或 `just foo bar`
- 调用：`just bar b` / `just bar::b`；`just --list foo::bar`
- 工作目录默认子模块文件所在目录；`justfile()` 恒指根，`source_file()`/`module_file()` 指当前文件
- `# doc` 紧贴 `mod foo` 显示于 `--list`

## 调用他处

```sh
just foo/build  # (cd foo && just build)
just foo/       # (cd foo && just) 默认配方
just foo/a b    # 同 justfile 多配方
```

## Fallback / 全局 / Markdown / Script

```just
set fallback  # 缺配方向父目录查找，遇 fallback=false 止
```

全局：`just --global-justfile`/`-g` 依次 `$XDG_CONFIG_HOME/just/justfile` → `~/.config/just/justfile` → `~/justfile` → `~/.justfile`；别名 `alias j=just`、`alias .j='just --justfile ~/.user.justfile --working-directory .'`。

Markdown：`just --justfile README.md build` 提取无缩进 ```just 块。

可执行：`#!/usr/bin/env just --justfile` + `chmod +x`；保调用目录加 `--working-directory .`，Linux 用 `env -S`。
