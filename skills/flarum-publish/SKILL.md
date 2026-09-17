---
name: flarum-publish
description: 发布文章（主题）到 Flarum 论坛，支持通过 REST API 创建讨论、按名称匹配标签、将文章配图转存到论坛图床（fof/upload）；也可将 GitHub 项目链接整理为中文文章后发布。标签列表缓存于 ~/.cache/flarum_idev_tags，支持默认标签组与 AI 项目标签组，可按项目语言自动追加语言标签。当用户要求发布/投稿文章到 Flarum 论坛、同步内容到论坛、把图片转存到论坛图床，或要求把 GitHub 项目整理成论坛文章时使用。
metadata:
  version: "1.10.0"
---

# Flarum 文章发布

通过 Flarum REST API 将一篇文章发布为论坛讨论（discussion）。

> API 依据官方文档：<https://github.com/flarum/docs/blob/main/docs/rest-api.md>（JSON:API 规范）。

## 目录

- [环境变量](#环境变量)
- [网络规则（中国网络代理）](#网络规则中国网络代理)
- [认证](#认证)
- [发布流程](#发布流程)
- [查重](#查重)
- [标签策略](#标签策略)
- [API 端点](#api-端点)
- [错误处理](#错误处理)
- [图片选择与图床转存](#图片选择与图床转存)
- [图片压缩与转存（>1MB 场景）](#图片压缩与转存1mb-场景)
- [使用脚本](#使用脚本)
- [约束](#约束)

## 环境变量

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `FLARUM_URL` | 是 | 论坛地址，如 `https://forum.example.com`（末尾不带 `/`） |
| `FLARUM_TOKEN` | 是 | API Key 或 Access Token（见下方认证说明） |
| `FLARUM_USER_ID` | 否 | 以指定用户身份发布，配合 API Key 使用（`userId=`） |

任一必填变量缺失时，向用户询问，不要猜测。

## 网络规则（中国网络代理）

当环境变量 `IS_CHINA` 的值为 `1`（中国网络环境）时，在搜索或下载文件时，若链接命中下方「代理域名清单」中的域名，必须在其前面添加前缀 `https://filetas.asfd.cn`。

### 代理域名清单

| 域名 | 改写示例 |
| --- | --- |
| raw.githubusercontent.com | `https://filetas.asfd.cn/https://raw.githubusercontent.com/xxx` |

后续发现其他需要走代理的域名，直接在上表末尾追加一行即可（仅填域名与示例）。

若访问未在清单中的域名或链接失败（如超时、连接被重置），可先按上述方式将该域名加入清单并加前缀 `https://filetas.asfd.cn` 后，重新抓取尝试。

### 代理不可用时的兜底（GitHub raw）

代理本身也可能失败（实测出现过 `CONNECT tunnel failed, response 502`）。抓取 GitHub 仓库内的文件（README、图片等）时，按以下顺序尝试，任一步成功即停止：

1. 直连原始地址；
2. `raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>` → 改用 GitHub Contents API，可直连：
   ```bash
   curl -fsSL -H "Accept: application/vnd.github.raw" \
     "https://api.github.com/repos/<owner>/<repo>/contents/<path>?ref=<ref>"
   ```
3. 加代理前缀 `https://filetas.asfd.cn/<原始地址>`。

`scripts/upload_image.sh` 已内置这套降级逻辑，下载图片时不必手工处理。

## 认证

两种方式任选其一：

1. **API Key**（推荐）：在数据库 `api_keys` 表中手动创建，`Authorization` 头格式为 `Token <key>; userId=<id>`。
2. **Access Token**：调用 `POST /api/token`，用用户名密码换取临时 token（session 类型，1 小时过期）：

   ```bash
   curl -s -X POST "$FLARUM_URL/api/token" \
     -H "Content-Type: application/json" \
     -d '{"identification": "<用户名>", "password": "<密码>"}'
   # 返回 {"token": "...", "userId": "1"}
   ```

若用户只提供了用户名和密码，先用上述接口换 token，再发布；不要把密码写入任何持久文件。

**Token 类型**（仅 Access Token）：

- `session`：默认，1 小时不活动即过期。
- `session_remember`：请求时指定 `remember=1` 可获取，5 年不活动过期。
- `developer`：永不过期，只能手动在数据库中创建。

**注意**：全局登出（`POST /logout?global=1`）或修改密码会删除该用户的所有 Access Token。

## 发布流程

1. **准备内容**（两条路径任选）：
   - **用户提供文章/文件**：确认标题与正文。正文使用 Markdown（Flarum 首帖支持 Markdown 格式存储）。若用户提供的是文件路径，读取全文作为正文；若未提供标题，从正文提炼。
   - **用户提供 GitHub 项目链接**（如 `https://github.com/<owner>/<repo>`）：按 [docs/github-article.md](docs/github-article.md) 的工作流采集仓库信息（API 元数据 + README），套用 [examples/demo.md](examples/demo.md) 模板整理成中文文章（成品参照 [examples/openshot.md](examples/openshot.md)），**保存为临时文件（默认 `/tmp/article.md`）**，再发布。注意：标题为 `<项目名称>：<总结性定位>`，**从 README 总结提炼、20 汉字以内、不照搬 GitHub API 的 description**（见 [docs/github-article.md](docs/github-article.md) 写作要求）。**标题与正文第一行必须一致**：正文第一行写 `# <标题>`（带 `# ` 前缀的 Markdown 一级标题），发布时传给 `publish.sh` 的标题参数为去掉 `# ` 前缀的同一字符串，两者内容完全一致。
2. **查重**：从标题提取项目名称，搜索论坛检查是否已存在该项目讨论（见[查重](#查重)）。已存在时向用户展示已有讨论并询问是否仍要发布。
3. **确认信息**：发布前向用户展示 标题 / 正文摘要 / 目标标签 / 图片（如有），确认后再发布。这是对外可见的公开操作，必须经用户确认。图片需展示完整 URL 供用户点击查看后自行选定，**确认选图后才转存到图床**（见[图片选择与图床转存](#图片选择与图床转存)）。
4. **确定标签**：按 [标签策略](#标签策略) 选择标签组。默认组 `[55,57]`（开源项目、开源社区），AI 项目组 `[63,86]`（人工智能、AI 项目）。GitHub 项目还需追加语言标签（见标签策略）。最终标签以逗号分隔的 ID 传给 `publish.sh`。
5. **发布**：调用 `scripts/publish.sh`（见[使用脚本](#使用脚本)）。
6. **验证**：脚本输出新讨论的 ID 与链接（`$FLARUM_URL/d/<id>`），向用户报告。

## 查重

发布前检查论坛是否已存在相同项目的讨论，避免重复发布。

### 提取项目名称

- 标题格式为 `<项目名>：<描述>`（如「Windmill：开源的开发者平台」）时，冒号前的部分即项目名（「Windmill」）。
- 无冒号时：GitHub 项目用仓库名（`<owner>/<repo>` 的 `<repo>` 部分）；普通文章用标题本身。

### 搜索论坛

按以下顺序依次尝试，**两层搜索都未命中**才可判定「未存在」：

#### 第一层：讨论标题搜索（`/api/discussions`）

```bash
curl -s --globoff "$FLARUM_URL/api/discussions?filter[q]=<项目名>"
```

- 注意 `[q]` 方括号需 curl 加 `--globoff` 或 URL 编码。
- 响应 `data[].attributes.title` 为匹配的讨论标题，逐一检查是否为同一项目。
- **局限**：该搜索不一定能覆盖所有讨论（项目名不在标题中时可能搜不到）。此时必须进入第二层，不可直接判定「未存在」。

#### 第二层：帖子搜索（`/api/posts`）

第一层无结果时，改用帖子接口搜索兜底：

```bash
curl -s --globoff "$FLARUM_URL/api/posts?filter[q]=<项目名>"
```

- 响应 `data[]` 为匹配的帖子，每项的 `relationships.discussion.data.id` 为所属讨论 ID。
- **取主题标题**：对去重后的讨论 ID 逐一调用 `GET /api/discussions/<id>`，从 `data.attributes.title` 读取主题标题。
- **判断方式与第一层相同**：检查这些主题标题中是否有同项目的讨论。

也可用页面搜索辅助核对：浏览器打开 `$FLARUM_URL/?q=<项目名>`（如 `https://forum.example.com/?q=Windmill`），所见即所得。

### 判定规则

- 第一层命中同项目讨论 → 已存在。
- 第一层未命中、第二层帖子搜索取到的主题标题中存在同项目讨论 → 已存在。
- 两层均未命中 → 未存在，继续正常发布流程。
- 项目名过短或过于通用（如 "app"、"tool"）导致结果过多或无有效结果时，用 GitHub 完整仓库名（`<owner>/<repo>`）或项目全名重新搜索确认。

## 标签策略

### 标签缓存

标签列表缓存于 `~/.cache/flarum_idev_tags`（Flarum `GET /api/tags?include=parent` 的原始 JSON 响应）。

- 文件不存在时，运行 `scripts/fetch_tags.sh` 自动获取并保存（`publish.sh` 在需要解析标签名称时也会自动调用）。
- 刷新缓存：`scripts/fetch_tags.sh --force`。
- 查看可用标签：直接读取缓存文件，或运行 `fetch_tags.sh`（已存在时输出摘要）。

### 常用标签组

| 分组 | Tag IDs | 标签 | 适用场景 |
| --- | --- | --- | --- |
| 默认（开源项目） | `55, 57` | 开源项目、开源社区 | 一般开源项目 |
| AI 项目 | `63, 86` | 人工智能、AI 项目 | AI / LLM / 机器学习相关项目 |

### 标签数量限制

**最终标签总数最多 3 个，2–3 个才正确**。超出时按以下优先级裁剪，保留前 3 个：

1. 基础标签组（默认组或 AI 组，2 个）；
2. 语言标签（1 个）。

即 GitHub 项目最多为「基础组 2 个 + 语言 1 个 = 3 个」；未匹配到语言标签时为 2 个。任何情况下都不得把 4 个及以上标签传给 `publish.sh`。

### 标签选择规则

1. **判断项目类型**：根据项目描述、README 内容、GitHub `topics` 等判断是否为 AI 相关项目。
   - 涉及 LLM、大模型、机器学习、深度学习、AI 工具/平台/教程、自然语言处理、计算机视觉等 → AI 项目，使用 `[63, 86]`。
   - 其他 → 默认组 `[55, 57]`。
   - 无法确定时，向用户确认。

2. **追加语言标签**（GitHub 项目，**自动化步骤，无需用户指定**）：从 GitHub API 获取项目占比最大的语言（`GET /repos/<owner>/<repo>` 返回的 `language` 字段），在标签缓存中查找匹配的语言标签并自动追加。用户只需确认标签组（步骤 1）与最终标签列表，不参与语言标签的选择。
   - GitHub 语言 → Flarum 标签对照（slug 不区分大小写匹配）：

     | GitHub 语言 | Flarum slug | Tag ID |
     | --- | --- | --- |
     | Python | `python` | 21 |
     | Go | `go` | 18 |
     | Rust | `rust` | 20 |
     | PHP | `php` | 19 |
     | JavaScript | `javascript` | 43 |
     | TypeScript | `typescript` | 58 |
     | Java | `java` | 59 |
     | C / C++ | `cpp` | 39 |
     | C# | `csharp` | 46 |
     | Ruby | `ruby` | 78 |
     | Dart | `dart` | 60 |
     | Kotlin | `kotlin` | 68 |
     | Swift | `swift` | 84 |
     | Shell | `shell` | 44 |
     | Lua | `lua` | 22 |
     | Zig | `zig` | 72 |
     | Vue | `vue` | 27 |
     | HTML | `html` | 5 |
     | PowerShell | `powershell` | 83 |
     | Dockerfile | `docker` | 26 |

   - 以上对照表为已知映射；遇到未列出的语言时，从标签缓存中按名称/slug 模糊匹配，匹配不到则跳过，不追加。
   - 最终标签组 = 基础标签组 + 语言标签（去重），**总数最多 3 个**（见[标签数量限制](#标签数量限制)）。

3. **传给脚本**：最终标签组以逗号分隔的 ID 传给 `publish.sh` 的第三个参数，如 `"$SKILL_PATH/scripts/publish.sh" "标题" /tmp/article.md "55,57,21"`。

## API 端点

各端点（获取 token、创建讨论、搜索、标签、fof/upload 上传）的请求示例与响应字段说明见 [references/api.md](references/api.md)。**需要构造请求、核对字段或排查响应结构时再加载该文件**；常规发布直接用脚本即可。

## 错误处理

Flarum 遵循 [JSON:API error spec](https://jsonapi.org/format/#errors)，读取响应 `errors[]` 数组：

| 状态码 | code | 含义与处理 |
| --- | --- | --- |
| 400 | `csrf_token_mismatch` | `Authorization` 头缺失或无效，Flarum 回退到了 cookie 会话认证。检查 token 与头部格式 |
| 422 | `validation_error` | 字段校验失败，`source.pointer` 指出无效字段（如 `/data/attributes/title`），`detail` 为具体原因；同一字段可能同时有多条错误 |
| 401/403 | — | 认证失败或无权限（如无发帖权限、recaptcha 插件拦截） |

## 图片选择与图床转存

当文章需要配图时（尤其是 GitHub 项目），**必须由用户确认是否添加图片以及选择哪张图片**，不要自动指定。

**关键顺序：先给用户看 URL，确认选图之后才转存。** 不要未经确认就把图片往论坛图床上传。

### 流程

1. **收集候选图片**：从 README 中提取所有图片引用（Markdown `![alt](path)` 或 HTML `<img src="path">`），过滤掉徽章（shields.io、badge、sponsor 图标）等非实质图片。
2. **拼接完整 URL**：相对路径拼接为 `https://raw.githubusercontent.com/<owner>/<repo>/<分支>/<路径>`。
3. **先在对话中输出图片链接（弹出选择框之前）**：把每个候选图片按「`<简短描述>: <完整URL>`」格式逐行输出到对话中，每行一个，如：

   ```
   架构图: <https://example.com/example.png>
   效果对比图: <https://example.com/compare.png>
   ```

   目的是让用户能直接点击打开查看每张图片，再据此决定选择框里选哪些。**必须先完成这一步输出，再弹出选择框。**

4. **展示候选并等待用户确认（在转存之前）**：用提问工具（如 `AskUserQuestion`）展示候选图片，每个选项须：
   - `label`：简短描述（如「架构图」「效果对比图」「hero 图」）。
   - `description`：**完整图片 URL**，与上一步对话中输出的对应行一致，方便再次点击查看。
   - 提供「不添加图片」选项。
   - 多张图片时可允许多选。
   - 若某个候选地址已失效（如 404），不要塞进选项；可改用项目官网等来源的可用图片，并在选项描述里注明来源。
5. **检查大小并转存到图床**：用户选定后，先用 `curl -sIL` 检查每张图的大小（取 `content-length`，无则下载到本地临时文件用 `stat -c%s` 取字节数）：
   - **≤1MB**：直接用 `scripts/upload_image.sh` 转存到论坛图床（见[使用脚本](#使用脚本)），脚本会输出图床地址。用户明确要保留原始地址时，可跳过转存。
   - **>1MB**：不直接转存，进入 [图片压缩与转存（>1MB 场景）](#图片压缩与转存1mb-场景) 流程——用 `oxipng` / `rimage` 尝试压缩；压缩后 <1MB 则转存，两工具都压不下来（失败或仍 ≥1MB）则直接引用原图 URL（**不加代理前缀**）。
6. **写入正文**：以 `![<alt>](<图床URL>)` 格式插入 `## 主要功能` 列表之后、`---` 分隔线之前。**图床地址保持协议相对形式，即 `//host/path`，不要写成 `https://host/path` 或 `http://host/path`**：

   ```markdown
   ![ECC 概览](//flarum-images.w.idev.top/2026-09-15/1789468836-466910-ecc-hero.png)
   ```

### 注意事项

- **正文图片地址一律使用协议相对形式**（`//<图片域名>/<日期>/<hash>-<name>.<ext>`）：不加 `http:` / `https:` 前缀，浏览器会按页面自身的协议（论坛是 https）解析。这是本站正文的既定写法——站内已有帖子的图片均为 `<img src="//flarum-images...">` 形式；写成带协议的绝对地址同样能显示，但风格不一致。
- `raw.githubusercontent.com` 在部分网络下不可达，不适合直接作为正文图片地址。
- 转存拿到的地址必须**回填进正文**：图片托管在图床不等于正文引用了它，漏了这一步读者看到的仍是打不开的原图地址。
- 图片若自行下载到本地，注意工作区临时文件不持久，下载与转存应在同一次操作内完成。
- 论坛图片有体积上限（实测 4096 kb），超限会被拒绝；`upload_image.sh` 会在上传前拦下超过 4 MB 的文件。

## 图片压缩与转存（>1MB 场景）

当候选图片 >1MB 时，不直接转存，而是先用本地压缩工具尝试压到 <1MB，再转存到论坛图床；若两工具都压不下来（压缩失败或压缩后仍 ≥1MB），则回退到原图 URL（**不加代理前缀**）。

### 工具安装（未安装时自动安装）

运行前检查 `oxipng` 与 `rimage` 是否已安装，缺失则用下列命令安装（安装脚本由用户托管于 `fx4.cn`）：

```bash
which oxipng >/dev/null 2>&1 || curl -L fx4.cn/oxipng | bash
which rimage >/dev/null 2>&1 || curl -L fx4.cn/rimage | bash
```

安装后验证：`oxipng --version` 与 `rimage --version` 应能正常执行。

**沙箱 / 受限环境下的两个坑（实测）**：

1. **PATH 里可能没有 `/usr/local/bin`**，导致 `which oxipng` 误判为未安装——工具其实早就装好了。检测时按绝对路径兜底：
   ```bash
   for t in oxipng rimage; do
     p=$(command -v $t || echo "/usr/local/bin/$t")
     [ -x "$p" ] && echo "$t -> $p"
   done
   ```
   命中绝对路径后直接用绝对路径调用（`/usr/local/bin/oxipng ...`），别再跑安装脚本。
2. **`fx4.cn` 安装脚本在本机必失败**：它解压到 `/tmp`，而 `/tmp` 只有 10 MB 的 tmpfs，还会因 `Cannot change ownership to uid 1001` 报错退出。不要反复重试安装脚本；改为手动装（解压加 `--no-same-owner`，装到 PATH 内可写目录如 `~/.local/bin`）：
   ```bash
   tar --no-same-owner -xzf <包>.tar.gz -C <工作区目录>
   install -m 755 <包>/oxipng ~/.local/bin/oxipng
   ```
   （`/usr/bin`、`/usr/local/bin` 在沙箱里可能是只读的，写入前先 `touch` 测一下。）

### 压缩算法（两工具互相兜底）

对单个 >1MB 图片，按以下流程处理（两个工具互为兜底：一个不行就换另一个，不重复尝试已失败的工具）：

1. 下载原图到本地临时文件（受 [网络规则](#网络规则中国网络代理) 代理规则约束）。
2. 依次尝试 `oxipng` 与 `rimage`（顺序不限），**任一工具满足「压缩成功 且 结果 <1MB」即采用该产物并停止尝试**：
   - `oxipng -o max --strip safe --out <out.png> <in.png>`（仅处理 PNG；非 PNG 直接判定该工具不可用，换下一个）。注意 oxipng 10.x 的 `-o` 是优化级别、输出文件必须用 `--out`，写成 `... <in> -o <out>` 会报 usage 错误。实测：1.32 MB 的 PNG 用这条命令可压到 812 KB。
   - `rimage png --directory <输出目录> --suffix _min <in.png>`（通用格式，需带子命令如 `png`/`webp`/`mozjpeg`；输出到 `--directory` 并加 `--suffix`，不支持「输入+输出」两个位置参数写法）。**实测它对 PNG 反而会变大**（1.35 MB → 8 MB），所以 PNG 优先用 oxipng，rimage 只作兜底。
   - GIF / 动图两个工具都处理不了（oxipng 只吃 PNG，rimage 无 gif 子命令），会走到「两工具都失败」分支，直接引用原图 URL。
3. **命中（某工具成功且 <1MB）**：将该产物转存到论坛图床（如 `flarum-images.w.idev.top`），正文使用协议相对地址 `//host/path`。
4. **两工具都失败 / 结果仍 ≥1MB**：放弃压缩，直接引用原图 URL，**不加代理前缀**（即 `https://raw.githubusercontent.com/...` 原样，不套 `filetas.asfd.cn`）。

> 兜底判定：「压缩不了」= 命令报错、不支持该格式、或进程非零退出；「压缩后还是大于 1M」= 压缩成功但字节数 ≥1048576。任一情形都立即切换到另一个工具；两个都不行才回退原图 URL。

## 使用脚本

### publish.sh — 发布讨论

```bash
# 基本用法（无标签）
"$SKILL_PATH/scripts/publish.sh" "标题" /path/to/article.md

# 带标签（ID 或名称，多个用逗号分隔）
"$SKILL_PATH/scripts/publish.sh" "标题" /path/to/article.md "55,57,21"

# 正文从 stdin 读入
cat article.md | "$SKILL_PATH/scripts/publish.sh" "标题" -
```

正文也可用 `-` 从 stdin 读入。标签参数支持纯数字 ID（直接使用）或名称/slug（从 `~/.cache/flarum_idev_tags` 缓存解析；缓存不存在时自动调用 `fetch_tags.sh` 获取）。脚本依赖 `curl`、`python3` 与上述环境变量。

### fetch_tags.sh — 获取标签缓存

```bash
# 首次获取或检查缓存
"$SKILL_PATH/scripts/fetch_tags.sh"

# 强制刷新缓存
"$SKILL_PATH/scripts/fetch_tags.sh" --force
```

标签缓存文件：`~/.cache/flarum_idev_tags`（原始 API JSON 响应）。

### upload_image.sh — 图片转存到论坛图床

把图片（本地文件或远程 URL）转存到论坛图床，拿到国内可直连的地址后写进正文。

```bash
# 单个 URL（GitHub raw 会自动降级到 api.github.com / 代理前缀）
"$SKILL_PATH/scripts/upload_image.sh" \
  "https://raw.githubusercontent.com/<owner>/<repo>/main/assets/hero.png"

# 本地文件
"$SKILL_PATH/scripts/upload_image.sh" ./hero.png

# 多张一起转存
"$SKILL_PATH/scripts/upload_image.sh" ./a.png ./b.png
```

- 输出：每个输入一行「`<来源>` + Tab + `<图床URL>`」，其中图床地址为**协议相对形式**（`//host/path`），可直接粘进正文；确需绝对地址时自行补 `https:`。失败的行打到 stderr，脚本以非 0 退出。
- 依赖环境变量 `FLARUM_URL`、`FLARUM_TOKEN`（可选 `FLARUM_USER_ID`）；`IS_CHINA=1` 时启用代理前缀降级。
- 单文件上限 4 MB，超限会在上传前报错。
- **必须在用户确认选图之后才调用**（见[图片选择与图床转存](#图片选择与图床转存)）。

### 示例文件

- [examples/demo.md](examples/demo.md)：文章模板（占位符格式）。
- [examples/openshot.md](examples/openshot.md)：一篇完整的示例文章（Markdown 首帖正文，含标题、简介、功能列表、图片与外链）。对应的发布命令：

  ```bash
  "$SKILL_PATH/scripts/publish.sh" "OpenShot：开源的视频编辑软件" \
    "$SKILL_PATH/examples/openshot.md" "55,57"
  ```

由 GitHub 项目生成的待发布文章是临时产物，默认保存到 `/tmp`（如 `/tmp/article.md`），不落入 skill 目录；成品内容示例见 [docs/github-article.md](docs/github-article.md)。

## 约束

- **发布前必须经用户确认**标题、正文与标签。
- **图片必须先经用户确认选图，再转存到图床**；不得未经确认就往图床传图。
- **标签总数最多 3 个**（2–3 个正确），超限会被论坛拒绝或截断。
- 不得修改或删除论坛上已有的讨论（本 skill 只做创建）。
- 不要将 token、密码写入文件、日志或提交记录。
