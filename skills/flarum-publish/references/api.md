# Flarum REST API 端点参考

> 本文按需加载。接口字段、请求示例与错误形态的完整说明。规范依据：<https://github.com/flarum/docs/blob/main/docs/rest-api.md>（JSON:API 规范）。


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

### 上传图片：Upload file（fof/upload）

`POST /api/fof/upload`（需要带认证头；由 `fof/upload` 插件提供）

```bash
curl -X POST "$FLARUM_URL/api/fof/upload" \
  -H "Authorization: Token $FLARUM_TOKEN" \
  -F "files[]=@/path/to/image.png;type=image/png"
```

- **表单字段名必须是 `files[]`**。用 `image` / `file` / `upload` 等其它名字都会返回 `400 fof-upload.no_files_made_it_to_upload`（提示「请上传小于 4096 kb 的文件」），即使文件本身完全合法。
- 响应 `data[0].attributes`：`url`（图片地址，**协议相对形式** `//<图片域名>/<日期>/<hash>-<name>.<ext>`；论坛正文直接用它即可，不要在前面补 `http:` / `https:`）、`path`、`type`、`size`、`bbcode`、`uuid` 等。`url` 即正文应使用的地址。
- 大小上限 4096 kb，超限拒绝。
- 也可通过 `GET /api/fof/upload` 判断论坛是否装了这个插件：返回 405 表示路由存在（可上传），404 表示没有该插件（此时跳过转存，正文用原始地址）。

### 其他端点（参考，本 skill 不使用）

- `POST /api/users`：创建用户（`attributes.username` / `email` / `password`）。
- `POST /api/posts`：在已有讨论下回帖（`type: "posts"`，`attributes.content` + `relationships.discussion`）。

