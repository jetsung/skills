# 语法 — 配方与参数

## 配方

```just
# build the project — 紧贴上方的 # 为文档，显示于 --list
build:
  cargo build

quiet:
  @echo hidden  # @ 静默回显
may-fail:
  -false        # - 忽略错误；set guards 时用 ?
```

- 体每行 `sh -cu`（`set shell` 可改），每行独立 shell
- 默认：`[default]` 否则首配方；`set default-list := true` 则列清单
- 查找：当前目录向上，`justfile`/`.justfile` 大小写不敏感
- 调用：`just <r> [args]` / `just a b c`（依赖先于配方）

## 参数

```just
build target:                          # 必需
  echo {{target}}
test target tests="all":               # 可选默认值（可为任意表达式，含 +/&&/||// 时加括号）
  ./test --tests {{tests}} {{target}}
variadic *args:                        # 可变
  echo {{args}}
exported $VAR:                         # 导出参数
  echo $VAR

arch := "wasm"
test2 triple=(arch + "-unknown-unknown") input=(arch / "input.dat"):
  ./test {{triple}}
```

- 传参：`just build myproj`；依赖传参 `default: (build "main")` / `(build target)` / `build: (_build target)`
- 括号语法必用于向依赖透传

### [arg] 标志（>=1.45）

```just
[arg(env, short="e", long="env")]
[arg(verbose, value="true")]  # flag
run env verbose="":
  echo {{env}} verbose={{verbose}}
```

`pattern` 正则、`short`/`long`/`value`/`min`/`max`/`multiple` 详见 `raw.md` Attributes。

### 分词规避

`{{arg}}` 会被 shell 分词，用 `quote()` / `shell()` 或导出后 `"$VAR"`；`set positional-arguments` + `[positional-arguments]` 得 `$1`/`$@`。

## 依赖与并行

```just
test: build           # 依赖先执行
  ./test
baz: foo::bar         # 跨模块
push target: (build target)
  echo {{target}}
a && b                # b 仅 a 成功才跑
[parallel]
deps: a b c           # 并行
```

`just test build` 仍先 `build`；`&&` 链失败短路。

## 组 / 别名 / 私有

```just
[group('build')]
compile:
  cc main.c -o main
alias b := compile
[private]
_hidden:
  echo secret
[doc("custom")]
compile2:
  cc main.c -o main
```

`--list` 按组/字母，`--unsorted` 保序，`--list-heading`/`--list-prefix` 定制；`[private]` 不列于 `--list`/`--summary`/`--choose`。

## 重复定义

```just
set allow-duplicate-recipes
set allow-duplicate-variables
foo:
  echo first
foo:
  echo second  # 后者覆盖；import 场景见 organization.md
```

## 细节

- 缩进 `--fmt` 统为 4 空格，`set indentation` 可改
- `if`/`for`/`while` 可在配方外赋值；体内多行用 `\` 或 shebang/`[script]`
- `{{{{` → `{{`
