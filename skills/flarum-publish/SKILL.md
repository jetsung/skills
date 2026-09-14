---
name: flarum-publish
description: 发布文章（主题）到 Flarum 论坛，支持通过 REST API 创建讨论、按名称匹配标签；也可将 GitHub 项目链接整理为中文文章后发布。标签列表缓存于 ~/.cache/flarum_idev_tags，支持默认标签组与 AI 项目标签组，可按项目语言自动追加语言标签。当用户要求发布/投稿文章到 Flarum 论坛、同步内容到论坛，或要求把 GitHub 项目整理成论坛文章时使用。
metadata:
  version: "1.8.0"
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
- [图片选择](#图片选择)
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
3. **确认信息**：发布前向用户展示 标题 / 正文摘要 / 目标标签 / 图片（如有），确认后再发布。这是对外可见的公开操作，必须经用户确认。图片需展示完整 URL 供用户点击查看。
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

### 认证：获取 Access Token

`POST /api/token`

```json
{
  "identification": "Toby",
  "password": "pass7word"
}
```

返回 `{"token": "...", "userId": "1"}`。

### 发布讨论：Create discussion

`POST /api/discussions`

```json
{
  "data": {
    "type": "discussions",
    "attributes": {
      "title": "Lorem Ipsum",
      "content": "Hello World"
    },
    "relationships": {
      "tags": {
        "data": [{ "type": "tags", "id": "1" }]
      }
    }
  }
}
```

- `attributes.title`：标题（必填）；`attributes.content`：首帖正文（必填，支持 Markdown）。
- `relationships.tags`：可选，`data` 为标签对象数组（`{"type": "tags", "id": "<标签ID>"}`），不支持标签的论坛需整体省略。
- 响应 `data.id` 即新讨论 ID，讨论链接为 `$FLARUM_URL/d/<id>`。

### 查询讨论列表：List discussions

`GET /api/discussions`

- 无需认证（仅返回访客可见内容）；支持分页 `?page[offset]=20`。
- 响应 `data[].attributes` 含 `title`、`slug`、`commentCount`、`createdAt` 等；`relationships.tags.data[].id` 为标签 ID；`included` 中含标签/用户/首帖详情（首帖 `attributes.contentHtml`）。

### 读取单篇讨论：Get discussion

`GET /api/discussions/<id>`

- 响应 `included` 中，`relationships.firstPost.data.id` 对应的帖子含 `attributes.contentHtml`（首帖正文）；`relationships.tags.data[].id` 为标签 ID（可在 `included` 中查到标签名称）。
- **注意**：部分站点的 `include=posts` 参数不可用，应直接请求 `GET /api/discussions/<id>` 后从 `included` 中提取。
- 可用于将论坛已有文章作为素材整理新文章。

### 搜索帖子：Search posts

`GET /api/posts?filter[q]=<关键词>`

- 用于查重的第二层兜底：第一层 `/api/discussions` 搜不到时，改搜帖子接口。
- 响应 `data[]` 中每项的 `relationships.discussion.data.id` 为所属讨论 ID。
- 取主题标题：对去重后的讨论 ID 调用 `GET /api/discussions/<id>` 读取 `data.attributes.title`，再按标题判断是否已存在同项目讨论（与第一层判断方式相同）。
- 未认证时仅返回访客可见帖子。

### 查询标签：Get tags

`GET /api/tags`

- 响应 `data`（或 `included`）中每个标签含 `id`、`attributes.name`、`attributes.slug`、`attributes.color`、`attributes.icon` 等。
- 未认证时仅返回访客可见的标签。

### 其他端点（参考，本 skill 不使用）

- `POST /api/users`：创建用户（`attributes.username` / `email` / `password`）。
- `POST /api/posts`：在已有讨论下回帖（`type: "posts"`，`attributes.content` + `relationships.discussion`）。

## 错误处理

Flarum 遵循 [JSON:API error spec](https://jsonapi.org/format/#errors)，读取响应 `errors[]` 数组：

| 状态码 | code | 含义与处理 |
| --- | --- | --- |
| 400 | `csrf_token_mismatch` | `Authorization` 头缺失或无效，Flarum 回退到了 cookie 会话认证。检查 token 与头部格式 |
| 422 | `validation_error` | 字段校验失败，`source.pointer` 指出无效字段（如 `/data/attributes/title`），`detail` 为具体原因；同一字段可能同时有多条错误 |
| 401/403 | — | 认证失败或无权限（如无发帖权限、recaptcha 插件拦截） |

## 图片选择

当文章需要配图时（尤其是 GitHub 项目），**必须由用户确认是否添加图片以及选择哪张图片**，不要自动指定。

### 流程

1. **收集候选图片**：从 README 中提取所有图片引用（Markdown `![alt](path)` 或 HTML `<img src="path">`），过滤掉徽章（shields.io、badge）等非实质图片。
2. **拼接完整 URL**：相对路径拼接为 `https://raw.githubusercontent.com/<owner>/<repo>/<分支>/<路径>`。
3. **展示并选择**：用 `ask` 工具向用户展示候选图片，每个选项须：
   - `label`：简短描述（如「架构图」「效果对比图」）。
   - `description`：完整图片 URL（方便用户点击查看）。
   - `preview`：可选，渲染图片预览供直接查看。
   - 提供「不添加图片」选项。
   - 多张图片时可设 `multi: true` 允许多选。
4. **写入正文**：用户选定后，以 `![<alt>](<完整URL>)` 格式插入 `## 主要功能` 列表之后、`---` 分隔线之前。正文中的图片 URL 使用原始地址（不加代理前缀）。

### 注意事项

- 若用户论坛有图片转存习惯（如将 GitHub 图片转存到论坛图床），提示用户先转存，正文使用转存后的 URL。

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
- **标签总数最多 3 个**（2–3 个正确），超限会被论坛拒绝或截断。
- 不得修改或删除论坛上已有的讨论（本 skill 只做创建）。
- 不要将 token、密码写入文件、日志或提交记录。
