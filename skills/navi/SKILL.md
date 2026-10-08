---
name: navi
description: 创建和管理 navi 交互式 cheatsheet（.cheat/.cheat.md）。当用户要求创建、修改、验证、分享 cheatsheet，或为某个 CLI/工具生成可交互命令模板（带变量 <var>、动态候选 $ var:、依赖 @ 扩展、多行 snippet）时使用本 skill。支持语法校验、路径定位、依赖继承与 fzf 选项定制。
compatibility: Requires navi binary for validation/preview; fzf or skim for interactive use. Pure file authoring needs only filesystem access.
metadata:
  version: "1.0.0"
  upstream: https://github.com/denisidoro/navi
  docs: https://github.com/denisidoro/navi/tree/master/docs
---

# Navi Cheatsheet 创作

用 `navi` 的 cheatsheet 语法创建可交互、可复用的命令行 cheats。`navi` 通过 `fzf`/`skim` 提供交互式选择与变量填充，适合把常用命令、团队规范沉淀为 cheats。

## 目录

- [创建前的决策](#创建前的决策)
- [快速开始](#快速开始)
- [Cheatsheet 语法总览](#cheatsheet-语法总览)
- [变量详解](#变量详解)
- [扩展与复用](#扩展与复用)
- [多行与 Markdown snippet](#多行与-markdown-snippet)
- [文件与路径](#文件与路径)
- [校验与预览](#校验与预览)
- [常见任务](#常见任务)
- [约束与易错点](#约束与易错点)

## 创建前的决策

1. **确定使用场景**：用户是为单个工具（如 `git`/`docker`/`kubectl`）还是跨工具主题（如 `devops`/`deploy`）创建 cheats
2. **确定输出位置**：见 [文件与路径](#文件与路径)；优先使用 `skills/navi/assets/templates/` 的模板作为起点
3. **确定变量来源**：哪些变量可枚举（`git branch`/`docker ps` 等），哪些需手输；是否需要列提取、分隔符、预览
4. **确定是否复用**：多个 cheat 共享变量时，用 `@ tag` 继承而非复制（详见 `references/syntax.md#extending-cheats`）

## 快速开始

### 最小可用示例

```sh
% git, code

# 切换分支
git checkout <branch>

$ branch: git branch | awk '{print $NF}'
```

- `%` 行：逗号分隔的 tags，作为 cheat 的入口与检索键
- `#` 行：单行功能描述
- 可执行行：含 `<变量>` 占位的命令模板
- `$` 行：为变量提供候选列表的命令（供 fzf 选择）

### 新建一个 cheatsheet 文件

```sh
# 1. 从模板复制
cp skills/navi/assets/templates/basic.cheat /tmp/my.cheat

# 2. 编辑内容（tags、描述、命令、变量）
# 3. 校验
skills/navi/scripts/validate.py /tmp/my.cheat

# 4. 放到 navi 路径测试
mkdir -p "$(navi info default-cheats-path 2>/dev/null || echo ~/.local/share/navi/cheats)"
cp /tmp/my.cheat "$(navi info default-cheats-path 2>/dev/null || echo ~/.local/share/navi/cheats)/my.cheat"
navi --path "/tmp"  # 或 navi --query "<关键词>" --best-match
```

> 模板与示例：`assets/templates/basic.cheat`（最小模板）、`assets/templates/advanced.cheat`（变量高级用法）、`assets/templates/markdown.cheat.md`（Markdown 块语法）。

## Cheatsheet 语法总览

cheatsheet 文件扩展名：`.cheat` 或 `.cheat.md`。按行解析，常见元素：

| 元素 | 前缀 | 说明 |
|------|------|------|
| Tags（cheat 标题） | `%` | 新 cheat 的开始，逗号分隔标签，如 `% git, code` |
| 描述 | `#` | 单行功能说明，如 `# 切换分支` |
| 元注释 | `;` | 被 navi 忽略的行；` ; raycast.icon:` 可设图标 |
| 预定义变量 | `$` | `$ <var>: <命令> --- <选项>` 为变量提供候选 |
| 继承扩展 | `@` | `@ <tags>` 继承其它 cheat 的变量上下文 |
| 可执行命令 | 无前缀 | 其它非空行即为命令模板，可含 `<var>` 占位 |

**解析规则**（来自 `src/parser.rs`）：

- `%` / `#` 出现时，会先 flush 上一条 cheat（若 comment/snippet 非空则写入 finder）
- 空行：在 snippet 内会追加 `LINE_SEPARATOR`，用于多行命令
- ` ``` `：切换 `inside_snippet` 状态；块内不解析 `$` 变量定义
- `$` 行支持续行：以 `\` 结尾则与下一行拼接后一起解析（`parse_variable_line`）
- `;` 行直接跳过（不影响 item）；`; raycast.icon:` 单独处理图标
- 重复 cheat（tags+comment+snippet 三元组 fnv 哈希相同）自动去重

> 详见 `references/syntax.md`（语法精读）、`references/variables.md`（变量与 fzf 选项）、`references/paths.md`（路径与配置）。

## 变量详解

### 命名与占位

- 变量名仅含 `[A-Za-z0-9_]`，在命令中写作 `<var_name>`
- 未定义 `$` 行的变量：用户自由输入
- 已定义 `$` 行的变量：用户从执行结果中选择（`Tab` 用输入值，`Enter` 用选中值）

### 预定义变量语法

```
$ <var>: <生成候选的 shell 命令> --- <fzf/取值选项>
```

`---` 后为可选项，支持（`references/variables.md` 有完整表）：

| 参数 | 含义 |
|------|------|
| `--column <n>` | 取第 n 列 |
| `--delimiter <regex>` | 列分隔正则，默认 `\s\s+` |
| `--header-lines <n>` / `--headers <n>` | 跳过表头行数 |
| `--multi` | 允许多选（`MultipleSelections`） |
| `--prevent-extra` | 仅允许从候选中选（`SingleSelection`） |
| `--expand` | 展开为多参数（`--map "… map::expand"`） |
| `--map <bash>` | 对选中值做映射转换 |
| `--fzf-overrides <arg>` | 透传 fzf 参数 |
| `--query/--filter/--header/--preview/--preview-window` | 透传 fzf |

`--multi` 优先于 `--prevent-extra`；`--expand` 底层为 `navi fn map::expand`。

### 依赖

- **隐式依赖**：变量命令中用 `<other_var>` 引用其它变量，如 `$ wallpaper: echo "<pictures>/wallpapers"`
- **显式依赖**：用 `$other_var` 形式，如 `$ y: echo "$x foo;$x bar" | tr ';' '\n'`

### 多参数变量

```sh
# 选中多个 json 文件后展开为: cat "a.json" "b.json"
cat <jsons>

$ jsons: find . -iname '*.json' -type f -print --- --multi --expand
```

## 扩展与复用

用 `@` 继承其它 cheat 的变量，实现"定义一次、多处复用"：

```sh
% dirs, common
$ pictures_folder: echo "/my/pictures"

% wallpapers
@ dirs, common
echo "<pictures_folder>/wallpapers"

% screenshots
@ dirs, common
echo "<pictures_folder>/screenshots"
```

- `@` 后的值为逗号分隔的 tags，与目标 cheat 的 `%` tags 按 fnv 哈希匹配
- 查找变量时先查自身 tags，再查依赖 tags（见 `src/structures/cheat.rs:VariableMap::get_suggestion`）

## 多行与 Markdown snippet

### 原生多行

```sh
% bash, foo

# 输出 foo 与 yes
echo foo
true \
   && echo yes \
   || echo no
```

### Markdown 代码块

````sh
% git, code

# 切换分支
```sh
git checkout <branch>
```

$ branch: git branch | awk '{print $NF}'
````

块内不解析 `$` 行；适合在 `.cheat.md` 中混合文档与命令。

## 文件与路径

| 场景 | 路径/方式 |
|------|-----------|
| 默认 cheats 目录 | `~/.local/share/navi/cheats/`（`navi info default-cheats-path`） |
| 临时/测试指定路径 | `navi --path '/some/dir:/other/dir'`（冒号分隔） |
| 环境变量覆盖 | `NAVI_PATH=/a:/b` |
| 配置文件指定 | `config.yaml` 中 `cheats.paths: [/path/a, /path/b]`（旧 `cheats.path` 已废弃） |
| 编译时默认值 | `NAVI_PATH` / `NAVI_CONFIG` 环境变量 |
| 配置文件默认位置 | `~/.config/navi/config.yaml`（`navi info default-config-path`） |

> 详见 `references/paths.md`。

## 校验与预览

```sh
# 语法校验（无需 navi 二进制）
python3 skills/navi/scripts/validate.py path/to/foo.cheat
python3 skills/navi/scripts/validate.py path/to/foo.cheat --strict

# 格式化检查（可选）
python3 skills/navi/scripts/validate.py path/to/foo.cheat --fix  # 原地规范化（去尾空格等）

# 交互式预览（需 navi + fzf）
navi --path "/tmp" --query "关键词"

# shell 脚本调用
navi --query "change branch" --best-match
branch="master" navi --query "change branch" --best-match
branch__query="master" navi --query "change branch" --best-match
branch__best="master" navi --query "change branch" --best-match
```

校验脚本检查项：tags 非空、`#` 描述存在、`<var>` 与 `$` 定义一致性、`---` 选项合法性、续行闭合、Markdown 块闭合、重复 cheat 提示等。

## 常见任务

### 为新工具创建 cheatsheet

1. 复制 `assets/templates/basic.cheat` 到目标路径，改 tags（如 `% docker, image`）
2. 为每个常用命令写 `# 描述` + 命令模板 + `$ 变量` 三件套
3. 需要表格列提取时加 `--column`/`--delimiter`，需多选加 `--multi --expand`
4. 运行 `scripts/validate.py`，再用 `navi --path` 预览

### 批量导入与分享

- 导入：`navi repo add https://github.com/<user>/<repo>` 或 `git clone <repo> "$(navi info default-cheats-path)/<user>__<repo>"`
- 浏览：`navi repo browse`
- 提交到官方：PR 到 `denisidoro/cheats`，或编辑 `featured_repos.txt`

### 兼容 tldr / cheat.sh

```sh
navi --tldr <query>
navi --cheatsh <query>
```

## 约束与易错点

- 变量名仅 `[A-Za-z0-9_]`；`<branch-name>` 非法，应为 `<branch_name>`
- `$` 行格式必须为 `$ var: command`（冒号分隔），缺冒号整行不被识别
- `---` 后的选项用 `shellwords` 解析，需正确引号包裹含空格的值（如 `--map "grep -q t && echo 1 || echo 0"`）
- Markdown 块内不解析 `$`；不要在块内定义变量
- `@` 继承依赖 tags 的 fnv 哈希精确匹配，拼写/空格差异会导致查找失败
- `cheats.path`（单数）已废弃，用 `cheats.paths`（数组）；脚本与文档已统一为新字段
- `navi repo add` 忽略 `NAVI_PATH`，始终写默认路径；需尊重 `NAVI_PATH` 时改用 `git clone` 到 `$NAVI_PATH` 下
- 通过 `shell.command` 执行变量命令，注意引号与平台差异（Windows 需 `powershell`）

## 按需加载的参考

| 文件 | 何时阅读 |
|------|----------|
| `references/syntax.md` | 精读语法、解析规则、元素优先级 |
| `references/variables.md` | 变量高级选项、列提取、map、依赖、多选 |
| `references/paths.md` | 路径解析优先级、配置、环境变量、repo 管理 |
| `references/examples.md` | 完整 cheatsheet 范例（含测试用例 `tests/cheats/*.cheat`） |
| `assets/templates/basic.cheat` | 新建 cheatsheet 起点 |
| `assets/templates/advanced.cheat` | 复杂变量/多选/map/预览示例 |
| `assets/templates/markdown.cheat.md` | Markdown 块写法示例 |

## 致谢

本 skill 内容整理自 [denisidoro/navi](https://github.com/denisidoro/navi) 官方文档与 `src/parser.rs` / `src/structures/` 源码。
