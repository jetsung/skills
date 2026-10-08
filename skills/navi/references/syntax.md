# Syntax 详解

本文精读 cheatsheet 语法与解析行为，依据 `docs/cheatsheet/syntax/README.md` 与 `src/parser.rs`。

## 文件扩展名

- `.cheat`：纯 cheatsheet 文本
- `.cheat.md`：可在 Markdown 代码块中写 snippet（` ``` ` 切换 `inside_snippet`）

## 元素一览

| 元素 | 前缀 | 示例 | 说明 |
|------|------|------|------|
| Tags | `%` | `% git, code` | 新 cheat 起点，逗号分隔；触发 `write_cmd` flush 上一条 |
| 描述 | `#` | `# 切换分支` | 功能说明；同样 flush 上一条 |
| 元注释 | `;` | `; raycast.icon: 🔧` | 忽略；唯 `; raycast.icon:` 写入 `item.icon` |
| 变量 | `$` | `$ branch: git branch … --- --column 2` | 见 `variables.md`；flush 上一条后写入 `VariableMap` |
| 依赖 | `@` | `@ dirs, common` | `VariableMap::insert_dependency`，按 fnv(tags) 建依赖图 |
| 命令 | 无 | `git checkout <branch>` | 追加到 `item.snippet`（`LINE_SEPARATOR` 连接） |

> `without_prefix` 实现：跳过首字符后 `trim()`，故 `%git,code` 与 `% git, code` 等价，也兼容全角空白。

## 解析流程（`Parser::read_lines`）

```
for line in lines:
  blank?          → snippet 非空则追加 LINE_SEPARATOR
  starts_with '%'? → flush 上一条 item; tags = without_prefix(line); snippet = ""
  starts_with '@'? → variables.insert_dependency(item.tags, without_prefix(line))
  starts_with '; raycast.icon:'? → item.icon = value
  starts_with ';'? → 忽略
  starts_with '#'? → flush; snippet=""; comment=without_prefix(line)
  variable?       → flush; snippet=""; 拼接续行(以 \ 结尾)后 parse_variable_line → insert_suggestion
  starts_with '```'? → inside_snippet = !inside_snippet
  else            → 追加到 snippet（LINE_SEPARATOR 连接）
end → flush 最后一条（忽略错误）
```

### 变量判定条件

```rust
!variable_cmd.is_empty()
|| (line.starts_with('$') && line.contains(':')) && !inside_snippet
```

- `inside_snippet == true` 时不识别 `$`
- 续行：`line.trim_end_matches('\\')` 拼接，直到不以 `\` 结尾才 `parse_variable_line`

### Flush 条件（`write_cmd`）

- `comment.is_empty() || snippet.trim().is_empty()` → 丢弃（不同时具备描述与命令则不展示）
- `visited_lines` 去重（tags+comment+snippet 的 fnv 哈希）
- `filter.allowlist/denylist/hash` 过滤（对应 `--tag-rules` 与 `--hash`）

## Tags 规则

- 逗号分隔，如 `% git, code, checkout`
- 检索时 `tag_rules` 如 `git,!checkout`：含 `!` 前缀为 denylist，其余为 allowlist（`gen_lists`）
- `@` 依赖查找：`VariableMap::get_suggestion` 先查自身 tags 的 fnv，再遍历依赖 tags

## 常见陷阱

- `%` / `#` 会清空 `snippet`，注意顺序：`%` → `#` → 命令 → `$` 是典型流
- 空行在 snippet 内有意义（追加分隔符），不要随意插入空行
- `;` 行完全忽略，不要指望它能作为分隔符影响解析
- 续行 `\` 必须在行尾且不含尾随空格（`trim_end_matches('\\')` 前无 trim）

## 最小正确结构

```sh
% <tags>

# <描述>
<命令含 <var>>

$ <var>: <生成候选的命令> --- <选项>
```

缺少 `#` 或命令则该条不会出现在 navi 列表中。
