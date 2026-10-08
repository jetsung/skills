# 路径、配置与仓库

依据 `docs/configuration/README.md`、`docs/cheatsheet/README.md`、`docs/usage/commands/info/README.md`、`docs/usage/commands/repo/README.md`、`src/config/`。

## Cheatsheets 路径解析优先级

navi 按以下顺序取首个有值的路径：

1. `$NAVI_PATH` 环境变量（冒号分隔）
2. 配置文件 `cheats.paths`
3. 编译时默认值（`directories-next` 决定的平台目录，常见为 `~/.local/share/navi/cheats/`）

> 旧字段 `cheats.path`（单值）自 `2.17.0` 废弃，`2.27.0` 移除；一律用 `cheats.paths`（数组）。

### 默认路径

```sh
navi info default-cheats-path   # 推荐
navi info cheats-path           # 已废弃，同上
```

### 运行时覆盖

```sh
navi --path '/some/dir:/other/dir'
NAVI_PATH='/some/dir:/other/dir' navi
```

### 配置文件写法

```yaml
cheats:
  paths:
    - /path/to/some/dir      # Unix
    - F:\\path\\to\\dir       # Windows 需转义
```

> `navi repo add` **忽略** `$NAVI_PATH`，始终写默认路径；需尊重自定义路径时用 `git clone`：

```sh
git clone https://github.com/<user>/<repo> "$(navi info default-cheats-path)/<user>__<repo>"
# 或尊重 NAVI_PATH 时
git clone https://github.com/<user>/<repo> "$NAVI_PATH/<user>__<repo>"
```

## 配置文件

### 默认位置

```sh
navi info default-config-path
navi info config-path           # 已废弃
```

默认 `~/.config/navi/config.yaml`，可被编译时 `$NAVI_CONFIG` 覆盖。

### 示例配置

```sh
navi info config-example        # 输出示例
navi info config-example > "$(navi info default-config-path)"
```

完整示例见 `docs/examples/configuration/config-example.yaml`，核心段：

```yaml
style:
  tag:     { color: cyan, width_percentage: 26, min_width: 20 }
  comment: { color: blue, width_percentage: 42, min_width: 45 }
  snippet: { color: white }

finder:
  command: fzf
  # overrides: --tac
  # overrides_var: --tac
  # delimiter_var: \s\s+

# cheats:
#   paths:
#     - /path/to/dir

# search:
#   tags: git,!checkout

shell:
  command: bash
  # finder_command: bash
```

### 样式与 FZF 覆盖

- `style.*.color`：`tag`/`comment`/`snippet` 列颜色
- `style.*.width_percentage` / `min_width`：列宽
- `finder.overrides`：cheat 选择阶段的 fzf 参数（等价 `NAVI_FZF_OVERRIDES`）
- `finder.overrides_var`：变量值选择阶段（`NAVI_FZF_OVERRIDES_VAR`）
- `finder.delimiter_var`：`--column` 的全局默认分隔符
- 全局：`FZF_DEFAULT_OPTS` 对所有 fzf 生效

```yaml
finder:
  command: fzf
  overrides: --height 3
  overrides_var: --height 3
```

### Shell 配置

```yaml
shell:
  command: bash          # 执行 $ 变量命令的 shell
  finder_command: bash   # fzf 内部使用的 shell
  forward_slash_path: true  # Windows Git Bash 等需开启
```

Windows 示例：

```yaml
shell:
  command: "\"C:/Program Files/Git/bin/bash.exe\""
  finder_command: "C:/Program Files/Git/bin/bash.exe"
  forward_slash_path: true
```

## Info 子命令

| 命令 | 说明 |
|------|------|
| `default-config-path` | 默认配置路径 |
| `default-cheats-path` | 默认 cheats 路径 |
| `config-example` | 示例配置内容 |
| `cheats-example` | 示例 cheat 内容 |
| `config-path` / `cheats-path` | 已废弃，别名 |

## Repo 子命令

| 命令 | 说明 |
|------|------|
| `navi repo add <url>` | 导入 cheatsheet 仓库（支持 HTTPS/SSH 的 git clone 格式） |
| `navi repo browse` | 浏览 `denisidoro/cheats/featured_repos.txt` 中的精选仓库 |

```sh
navi repo add https://github.com/denisidoro/cheats
navi repo add git@github.com:denisidoro/cheats
navi repo browse
```

精选仓库提交：PR 到 `denisidoro/cheats`，或编辑 `featured_repos.txt` 后 PR。

### 自动更新

navi 无内置自动更新，用 cron + git：

```sh
crontab -e
# 每天 11:00 拉取
0 11 * * * bash -c 'cd "$(navi info default-cheats-path)/<user>__<repo>" && git pull -q origin master'
```

## 其它用法

### tldr / cheat.sh 兼容

```sh
navi --tldr <query>
navi --cheatsh <query>
```

### 搜索键位

| 键 | 行为 |
|----|------|
| `Tab` | 优先使用输入的 query |
| `Enter` | 优先使用选中的候选项 |

### Shell 集成

```sh
navi --query "change branch" --best-match
branch="master" navi --query "change branch" --best-match          # 预设变量，跳过交互
branch__query="master" navi --query "change branch" --best-match   # 过滤候选
branch__best="master" navi --query "change branch" --best-match    # 选最佳匹配
```
