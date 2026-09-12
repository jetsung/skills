---
name: flarum-publish
description: 发布文章（主题）到 Flarum 论坛，支持通过 REST API 创建讨论、按名称匹配标签；也可将 GitHub 项目链接整理为中文文章后发布。当用户要求发布/投稿文章到 Flarum 论坛、同步内容到论坛，或要求把 GitHub 项目整理成论坛文章时使用。
metadata:
  version: "1.4.0"
---

# Flarum 文章发布

通过 Flarum REST API 将一篇文章发布为论坛讨论（discussion）。

> API 依据官方文档：<https://github.com/flarum/docs/blob/main/docs/rest-api.md>（JSON:API 规范）。

## 目录

- [环境变量](#环境变量)
- [网络规则（中国网络代理）](#网络规则中国网络代理)
- [认证](#认证)
- [发布流程](#发布流程)
- [API 端点](#api-端点)
- [错误处理](#错误处理)
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
   - **用户提供 GitHub 项目链接**（如 `https://github.com/<owner>/<repo>`）：按 [docs/github-article.md](docs/github-article.md) 的工作流采集仓库信息（API 元数据 + README），套用 [examples/demo.md](examples/demo.md) 模板整理成中文文章（成品参照 [examples/openshot.md](examples/openshot.md)），**保存为临时文件（默认 `/tmp/article.md`）**，再发布。注意：`# <项目名称>：<描述>` 一级标题既是讨论标题，也是文章正文的首行，需保留在正文文件的第一行。
2. **确认信息**：发布前向用户展示 标题 / 正文摘要 / 目标标签，确认后再发布。这是对外可见的公开操作，必须经用户确认。
3. **解析标签**（可选）：
   - 用户给出标签名称时，先查询标签 ID：`GET /api/tags`（响应的 `included` 或 `data` 中有各标签的 `id`、`attributes.slug`、`attributes.name`）。
   - 按名称或 slug 模糊匹配；匹配不到时列出可用标签让用户选择，不要随意指定 ID。
4. **发布**：调用 `scripts/publish.sh`（见[使用脚本](#使用脚本)）。
5. **验证**：脚本输出新讨论的 ID 与链接（`$FLARUM_URL/d/<id>`），向用户报告。

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

## 使用脚本

优先使用 `scripts/publish.sh`（`SKILL_PATH` 为本 skill 根目录的绝对路径）：

```bash
# 基本用法（无标签）
"$SKILL_PATH/scripts/publish.sh" "标题" /path/to/article.md

# 带标签（名称或 ID，多个用逗号分隔）
"$SKILL_PATH/scripts/publish.sh" "标题" /path/to/article.md "问答,教程"

# 正文从 stdin 读入
cat article.md | "$SKILL_PATH/scripts/publish.sh" "标题" -
```

正文也可用 `-` 从 stdin 读入。脚本依赖 `curl`、`python3`（用于构造 JSON，避免转义问题）与上述环境变量。

### 示例文件

- [examples/demo.md](examples/demo.md)：文章模板（占位符格式）。
- [examples/openshot.md](examples/openshot.md)：一篇完整的示例文章（Markdown 首帖正文，含标题、简介、功能列表、图片与外链）。对应的发布命令：

  ```bash
  "$SKILL_PATH/scripts/publish.sh" "OpenShot：开源的视频编辑软件" \
    "$SKILL_PATH/examples/openshot.md" "开源项目"
  ```

由 GitHub 项目生成的待发布文章是临时产物，默认保存到 `/tmp`（如 `/tmp/article.md`），不落入 skill 目录；成品内容示例见 [docs/github-article.md](docs/github-article.md)。

## 约束

- **发布前必须经用户确认**标题、正文与标签。
- 不得修改或删除论坛上已有的讨论（本 skill 只做创建）。
- 不要将 token、密码写入文件、日志或提交记录。
