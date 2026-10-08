# 完整示例

本文件汇总可用 cheatsheet 范例，来源：`docs/examples/cheatsheet/*.cheat`、`tests/cheats/*.cheat`、`docs/cheatsheet/syntax/README.md`。

## 官方最小示例

```sh
% git, code

# Change branch
git checkout <branch>

$ branch: git branch | awk '{print $NF}'
```

## 可交互 Demo（`docs/examples/cheatsheet/navi.cheat`）

```sh
% cheatsheets
 
# Download default cheatsheets
navi repo add denisidoro/cheats

# Browse for cheatsheet repos
navi repo browse

# Edit main local cheatsheets
f="$(navi info cheats-path)/main.cheat"
[ -f "$f" ] || navi info cheats-example > "$f"
${EDITOR:-nano} "$f"


% config

# Edit config file
f="$(navi info config-path)"
[ -f "$f" ] || navi info config-example > "$f"
${EDITOR:-nano} "$f"


% 3rd-party

# Search using tldr
navi --tldr "<query>"

# Search using cheatsh
navi --cheatsh "<query>"


% widget

# Load shell widget
shell="$(basename $SHELL)"; eval "$(navi widget $shell)"


% help

# Read command-line help text
navi --help

# Read project README.md
navi fn url::open "https://github.com/denisidoro/navi"
```

## 测试用例精選（`tests/cheats/more_cases.cheat`）

```sh
% test, ci/cd

# escape code + subshell
echo -ne "\033]0;$(hostname)\007"

# multi + column
myfn() {
    for i in $@; do
        echo -e "arg: $i\n"
    done
}
folders=($(echo "<multi_col>"))
myfn "${folders[@]}"

# second column: default delimiter
echo "<table_elem> is cool"

# second column: custom delimiter
echo "<table_elem2> is cool"

# return multiple results: single words
echo "I like these languages: "$(printf '%s' "<langs>" | tr '\n' ',' | sed 's/,/, /g')""

# with preview
cat "<file>"

# with map
echo "<mapped>"

# map can be used to expand into multiple arguments
for l in <phrases>; do echo "line: $l"; done

# Concatenate pdf files
files=($(echo "<files>"))
echo pdftk "${files[@]:-}" cat output <pdf_output>

$ files: echo 'file1.pdf file2.pdf file3.pdf' | tr ' ' '\n' --- --multi --fzf-overrides '--tac'
$ table_elem: echo -e '0  rust      rust-lang.org\n1  clojure   clojure.org' --- --column 2
$ table_elem2: echo -e '0;rust;rust-lang.org\n1;clojure;clojure.org' --- --column 2 --delimiter ';'
$ multi_col: ls -la | awk '{print $1, $9}' --- --column 2 --delimiter '\s' --multi
$ langs: echo 'clojure rust javascript' | tr ' ' '\n' --- --multi
$ mapped: echo 'true false' | tr ' ' '\n' --- --map "grep -q t && echo 1 || echo 0"
$ file: ls . --- --preview 'cat {}' --preview-window 'right:50%'
$ phrases: echo -e "foo bar\nlorem ipsum\ndolor sit" --- --multi --map "navi fn map::expand"
```

## 继承与多行

### 继承（`@`）

```sh
% dirs, common

$ pictures_folder: echo "/my/pictures"

% wallpapers
@ dirs, common

# Should print /my/pictures/wallpapers
echo "<pictures_folder>/wallpapers"

% screenshots
@ dirs, common

# Should print /my/pictures/screenshots
echo "<pictures_folder>/screenshots"
```

### 多行命令

```sh
% bash, foo

# This will output "foo\nyes"
echo foo
true \
   && echo yes \
   || echo no
```

### Markdown 代码块

````sh
% git, code

# Change branch
```sh
git checkout <branch>
```

$ branch: git branch | awk '{print $NF}'
````

### 变量依赖

```sh
# 隐式
echo "<wallpaper_folder>"

$ pictures_folder: echo "/my/pictures"
$ wallpaper_folder: echo "<pictures_folder>/wallpapers"
```

```sh
# 显式
echo <x> <y>
: <x>; echo <y>

$ x: echo "hello hi" | tr ' ' '\n'
$ y: echo "$x foo;$x bar" | tr ';' '\n'
```

## 自检清单

- [ ] 每个 cheat 都有 `%` tags + `#` 描述 + 至少一行命令
- [ ] 命令中的 `<var>` 与 `$ var:` 定义一一对应（未定义的应为有意手输）
- [ ] `--column`/`--delimiter`/`--map` 等引号闭合
- [ ] Markdown 块已闭合（成对 ```）
- [ ] `@` 依赖的 tags 拼写与目标 `%` 行完全一致
```

# 验证脚本可检测的项见 scripts/validate.py --help
