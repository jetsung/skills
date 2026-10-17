# 表达式、变量与函数

## 变量

```just
name := "value"
export name := "value"
unexport FOO
foo := "a" + "b"              # 拼接
bar := foo / "baz"            # 路径拼接恒 /
baz := `echo hi`              # backtick
qux := shell('echo hi')       # shell()
# set lazy 时未用不求值
```

右侧可为函数/条件/路径运算；`[env(NAME, VALUE)]` 仅单配方生效。

## 插值

```just
msg := "pre {{greeting}} suf"
esc := "{{{{ not interp }}"  # -> {{
s := '''
  hello
  world
'''
```

`{{expr}}` 于体/依赖/属性求值；`{{{{` 转义。

## 类型

字符串默认；列表需 `set unstable` + `set lists`；布尔为 `"true"`/`"false"` 字符串。

```just
set unstable
set lists
files := ["a.c", "b.c"]
```

## 条件与逻辑

```just
foo := if "a" == "b" { "yes" } else { "no" }
x := "a" && "b"  # 非空为真 -> "b"
```

## Backtick / shell()

```just
date := `date +%Y-%m-%d`
out := shell('echo $1 | tr a-z A-Z', 'hello')  # $1 首参，$@ 余参
```

均走 `set shell`。

## 常用函数

| 类 | 函数 |
|----|------|
| 系统 | `arch()` `os()` `os_family()` `num_cpus()` |
| 路径(可失败) | `absolute_path()` `canonicalize()` `extension()` `file_name()` `file_stem()` `parent_directory()` `without_extension()` |
| 路径(不可失败) | `clean()` `join()` `path_exists()` |
| 环境 | `env(k)` `env(k, d)` `require(name)` `which(name)` |
| 调用信息 | `invocation_directory()` `justfile()` `justfile_directory()` `source_file()` `module_file()` `just_executable()` `just_pid()` `just_version()` `is_dependency()` `num_jobs()` `recipe_name()` |
| 字符串 | `capitalize()` `kebabcase()` `snakecase()` 等；`trim()` `replace()` `replace_regex()` `quote()` `encode_uri_component()` |
| 哈希/随机 | `blake3()` `sha256()` `uuid()` `choose(n, alphabet)` |
| 时间/版本 | `datetime()` `datetime_utc()` `semver_matches(v, req)` |
| 样式 | `style(styles)` `style(styles, text)` |

常量 `HEX` `RED` `BOLD` `NORMAL` 等 ANSI 见 `raw.md` Constants；完整签名见 `raw.md` Functions。

## Sigils

`@` 静默、`-` 忽略错误、`?` 守卫（需 `set guards`），可组合 `@-`。
