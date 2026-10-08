# 变量与 Finder 选项

本文对应 `docs/cheatsheet/syntax/README.md#variables` 与 `src/parser.rs:parse_opts`。

## 变量基础

- 命令中占位：`<var>`，`var` 仅 `[A-Za-z0-9_]`（`VAR_LINE_REGEX = r"^\$\s*([^:]+):(.*)"`）
- 定义：`$ var: <shell 命令> --- <选项>`
- 未定义的 `<var>`：navi 提示用户手输
- 已定义的：执行 `$` 行的 shell 命令，将输出通过 fzf 让用户选择
- 交互键：`Tab` 优先用输入的 query，`Enter` 优先用选中项

## 选项分隔

```
$ var: <command> --- <opts>
```

- `---` 左侧为 shell 命令，右侧为选项字符串
- 选项字符串经 `shellwords::split` 解析，再按 `chunks(2)` 成对处理
- 无 `---` 则无选项（`command_options = None`）

## 支持的选项

`parse_opts` 实际支持：

| 写法 | 作用 | 类型 |
|------|------|------|
| `--multi` | 允许多选 | flag，无值（`SuggestionType::MultipleSelections`） |
| `--prevent-extra` | 仅允许选中项 | flag（`SingleSelection`）；`--multi` 存在时被覆盖 |
| `--expand` | 展开为多参数 | flag，设为 `map = "navi fn map::expand"` |
| `--column <n>` | 取第 n 列 | `--column 3` |
| `--map <bash>` | 对值做映射 | `--map "grep -q t && echo 1 || echo 0"` |
| `--delimiter <regex>` | 列分隔正则 | `--delimiter '\s\s+'` 或 `';'` |
| `--header-lines <n>` / `--headers <n>` | 表头行数 | 数值 |
| `--query <text>` | 初始 query | 字符串 |
| `--filter <text>` | 过滤器 | 字符串 |
| `--header <text>` | fzf header | 字符串 |
| `--preview <bash>` | 预览命令 | `--preview 'cat {}'` |
| `--preview-window <text>` | 预览窗口 | 字符串 |
| `--fzf-overrides <arg>` | 透传 fzf | 任意 fzf 参数 |

> 文档中另列的 `--delimiter`/`--column`/`--header-lines` 等转发到 fzf 的参数，解析逻辑与上表一致。

### SuggestionType

```
(multi, prevent_extra) = (true, _)  → MultipleSelections
                    (false, false) → SingleRecommendation
                    (false, true)  → SingleSelection
```

## 列提取

```sh
# 取第 3 列，首行为表头，分隔为 2+ 空白
docker rmi <image_id>

$ image_id: docker images --- --column 3 --header-lines 1 --delimiter '\s\s+'
```

- `finder.delimiter_var`（配置）为全局默认分隔符，可被 `--delimiter` 覆盖
- 取列后才是 `--map` 的输入

## Map 映射

```sh
echo <mapped>

$ mapped: echo 'false true' | tr ' ' '\n' --- --map "grep -q t && echo 1 || echo 0"
# 选中 false → 0，true → 1
```

`--expand` 本质是 `--map "navi fn map::expand"` 的语法糖。

## 多选与多参数

```sh
cat <jsons>

$ jsons: find . -iname '*.json' -type f -print --- --multi --expand
# 结果：cat "a.json" "b.json"
```

- `--multi` 让 fzf 多选
- `--expand` 把每行展开为独立引号参数，配合 `myfn "${arr[@]}"` 使用

## 预览

```sh
cat "<file>"

$ file: ls . --- --preview 'cat {}' --preview-window 'right:50%'
```

## 依赖

### 隐式依赖（`<var>`）

```sh
echo "<wallpaper_folder>"

$ pictures_folder: echo "/my/pictures"
$ wallpaper_folder: echo "<pictures_folder>/wallpapers"
# 执行 wallpaper_folder 命令时会先替换 <pictures_folder>
```

### 显式依赖（`$var`）

```sh
echo <x> <y>
: <x>; echo <y>

$ x: echo "hello hi" | tr ' ' '\n'
$ y: echo "$x foo;$x bar" | tr ';' '\n'
# y 的命令中 $x 会被替换为 x 的选中值
```

> 解析时 `$x` 与 `<x>` 都在 shell 命令执行前做文本替换；显式依赖适合在 `echo "$x …"` 这类 shell 变量上下文中使用。

## FZF 透传

```sh
$ with_overrides: echo -e "foo bar\nlorem ipsum" --- --fzf-overrides "--margin=15% --bind=ctrl-u:replace-query"
```

更多覆盖方式见 `docs/configuration/README.md#overriding-fzf-options` / `references/paths.md`。

## 校验要点

- `$` 行必须含 `:`，否则 `parse_variable_line` 报 `No variables…`
- `---` 后选项缺值（如 `--column` 无数字）报 `No value provided for the flag`
- 数值解析失败（如 `--column foo`）报 `invalid u8`
- 选项字符串缺闭合引号报 `missing closing quote`（`shellwords::split`）
