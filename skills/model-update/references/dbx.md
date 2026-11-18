# DBX 配置参考（`dbx.db` 的 `ai_configs` 表）

DBX 桌面端不把配置写在文件里，而是存在 **SQLite 库** `dbx.db` 的 `ai_configs` 表中：一个渠道 = 一条记录，模型列表存在记录内的 `models` 字段。真正的 schema 在 `config_json` 这一 JSON 列里。

表结构由本机数据库提取整理（无官方公开文档），完整说明见 `model-channel-sync` 技能的 `references/dbx.md`。

**写入范围**：只写用户数据目录下的 `dbx.db`（等价于其它平台的「用户级全局配置」），禁止修改项目内文件。

## 数据目录定位

优先级：`DBX_DATA_DIR` 环境变量（指向包含 dbx.db 的**目录**，不是文件本身）→ 平台默认：

| 平台 | 默认数据目录 |
|------|-------------|
| Linux | `~/.local/share/com.dbx.app` |
| macOS | `~/Library/Application Support/com.dbx.app` |
| Windows | `%APPDATA%\com.dbx.app` |

## 表结构（DDL）

```sql
CREATE TABLE ai_configs (
    id          TEXT PRIMARY KEY,            -- UUID v4
    name        TEXT NOT NULL UNIQUE,        -- 配置名称（渠道显示名）
    model       TEXT NOT NULL DEFAULT '',    -- 当前选中模型（冗余列）
    models      TEXT NOT NULL DEFAULT '[]',  -- 已保存模型列表（JSON 数组字符串，冗余列）
    config_json TEXT NOT NULL,               -- 完整配置（JSON 字符串，真正 schema 在这里）
    is_default  INTEGER NOT NULL DEFAULT 0   -- 默认配置标记，全局最多 1 个
);
CREATE UNIQUE INDEX idx_ai_configs_default ON ai_configs(is_default) WHERE is_default = 1;
```

**双写约束（关键）**：`model` / `models` 顶层列与 `config_json.model` / `config_json.models` 必须一致——DBX 读取时以 `config_json` 为主，但列表与搜索可能读顶层列，**只写一处会导致模型列表在界面上显示为空**。写入时 `model` 列 = `config_json.model`，`models` 列 = `JSON.stringify(config_json.models)`。

## 渠道（记录）字段

一条记录代表一个渠道，`config_json` 的字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `provider` | string | 供应商预设：`claude` / `openai` / `gemini` / `deepseek` / `qwen` / `minimax` / `ollama` / `openai-compatible` / `anthropic-compatible` / `custom`。**新建一律用 `openai-compatible`（OpenAI 兼容）或 `anthropic-compatible`**；旧版 `custom` 仍兼容，遇到可自动迁移 |
| `endpoint` | string | API 端点，即 `<PREFIX>_BASE_URL` 的真实值（去尾斜杠，**不含** `/chat/completions`） |
| `apiKey` | string | API 密钥，**明文存储、未加密** |
| `authMethod` | string | 认证方式，`"bearer"` |
| `apiStyle` | string | API 风格：`completions` / `responses` / `anthropic-messages` |
| `model` | string | 当前选中模型（与顶层 `model` 列双写一致） |
| `models` | array | 该渠道已保存模型列表（与顶层 `models` 列双写一致） |
| `contextWindow` / `maxOutputTokens` | number\|null | 上下文窗口 / 最大输出（可为 `null`） |
| `enableThinking` / `reasoningLevel` | bool / string | thinking 开关 / 推理强度（`"default"` 等） |
| `maxRetries` | number\|null | API 重试次数（默认 2，范围 0–10） |
| `customHeaders` | object | 自定义请求头（敏感值） |
| `proxyEnabled` / `proxyUrl` / `skipTlsVerify` | bool / string / bool | 代理与 TLS 设置 |
| `{codex,claudeCode,piAgent,opencode,cursor,grok,codebuddy,qoder}CliPath` / 同名 `CliEnv` | string\|null / object | 本地 CLI Agent 路径与额外环境变量 |

`provider` 与 `apiStyle` 的映射：`openai-completions` → `openai-compatible` + `completions`；`openai-responses` → `openai-compatible` + `responses`；`anthropic-messages` → `anthropic-compatible` + `anthropic-messages`。

## 模型（models 元素）字段

`models` 是**对象数组**，元素只有两个字段：

```json
[
  { "id": "deepseek-flash", "name": "Sense DeepSeek Flash" }
]
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 模型标识，原样传给 API |
| `name` | 是 | 显示名；缺失时 DBX 报 `missing field 'name'`，故必须写（上游无显示名时用 `id`） |

> 旧版 `["id1","id2"]` 字符串数组**已不再兼容**：DBX 启动时报 `invalid type: string "...", expected struct AiModelListItem` 并**阻塞启动**。读取时兼容旧格式，写入时一律转成对象数组。

## 新增渠道示例

一条新记录（`config_json` 展开后的形状）：

```json
{
  "provider": "openai-compatible",
  "apiKey": "sk-实际密钥值",
  "authMethod": "bearer",
  "endpoint": "https://token.sensenova.cn/v1",
  "model": "sensenova-6.8-flash-lite",
  "models": [
    { "id": "sensenova-6.8-flash-lite", "name": "Sense Sensenova 6.8 Flash Lite" },
    { "id": "deepseek-flash", "name": "Sense DeepSeek Flash" }
  ],
  "apiStyle": "completions",
  "customHeaders": {},
  "proxyEnabled": false,
  "proxyUrl": "",
  "skipTlsVerify": false,
  "enableThinking": true,
  "reasoningLevel": "default",
  "maxOutputTokens": null,
  "contextWindow": null,
  "maxRetries": null
}
```

顶层列同步写入：`id` = uuid4、`name` = 渠道显示名、`model` = `config_json.model`、`models` = `JSON.stringify(config_json.models)`、`is_default` = `0`（默认配置由用户在 DBX 设置里手动指定，脚本不改动）。

## 字段映射（上游 `/models` → DBX）

| 上游字段 | DBX 字段 | 说明 |
|----------|----------|------|
| `<PREFIX>_BASE_URL` 实值 | `config_json.endpoint` | 去尾斜杠；不拼 `/chat/completions`（与 codebuddy 相反） |
| `<PREFIX>_API_KEY` 实值 | `config_json.apiKey` | **写死明文实值**，不支持环境变量引用 |
| 渠道显示名 | 顶层 `name` 列 | 唯一约束，不可与既有记录重名 |
| `id` | `models[].id` | 保持上游原样，不擅自加/去前缀 |
| `name` / `display_name` | `models[].name` | 缺失时回退 `id` |
| `output_modalities` 含 `image`/`video`/`audio` 或 chat 实测 404 | — | 生图/非文本模型**不写入**（DBX 条目一律当聊天模型） |

`model`（当前选中模型）取同族最高版本：族键 = id 最后一段的开头连续字母，版本号 = 首个数字串；上游原序首个族作为兜底 `best`，避免排序错族。

## 更新已有渠道

- **渠道匹配**：先按 `config_json.endpoint`（baseUrl 去尾斜杠）精确匹配，其次按顶层 `name`（渠道显示名）；无匹配则新建记录；
- **模型合并**：向 `models` **追加**缺失对象（只增不删，已有条目不动），并双写顶层 `models` 列；
- **只动这些字段**：`model` / `apiKey` / `endpoint` / `apiStyle` / `provider` / `models` / `name`；已有记录的 `customHeaders`、代理、`skipTlsVerify`、`reasoningLevel`、`enableThinking`、CLI 路径等**不更新**；
- `provider = "custom"` 的旧记录可自动迁移为 `openai-compatible` / `anthropic-compatible`；
- `is_default` 不改动；与本次同步无关的记录保持不变。

## 操作前提

**写库前先退出 DBX 应用**（避免 SQLite 写锁与运行时覆盖）；只读查看可直接 `sqlite3 dbx.db`。

## 写入后校验

```bash
# 记录与本批模型可见
sqlite3 ~/.local/share/com.dbx.app/dbx.db \
  "SELECT name, model, is_default FROM ai_configs"

# 双写一致性（每行两个判据都应为 True）
python3 - <<'EOF'
import sqlite3, json, os
con = sqlite3.connect(os.path.expanduser('~/.local/share/com.dbx.app/dbx.db'))
for n, m, ms, cj in con.execute('SELECT name,model,models,config_json FROM ai_configs'):
    c = json.loads(cj)
    print(n, m == c['model'], json.loads(ms) == c['models'])
EOF
```

再确认：记录数只增不减、已有行的 `id` 与 `is_default` 未变、`models` 元素均为 `{id, name}` 对象、`apiKey` 为明文实值且输出中不出现明文。

排查启动阻塞：`tail -f ~/.local/share/com.dbx.app/database-backups/worker.log | grep -E "invalid ai_configs|missing field"` —— `expected struct AiModelListItem` 表示 `models` 仍是字符串数组，`missing field 'name'` 表示对象缺 `name`。

## 注意

- 每次真实写入前备份 `dbx.db.bak-YYYYMMDD`；`dbx.db` 含明文 `apiKey`，属敏感文件，**切勿提交到版本库或外发**，备份权限 `0600`；
- 报告只说明密钥长度/变化状态，绝不输出 `apiKey` 内容；
- DBX 无渠道层级嵌套（不像 pi/opencode 在 provider 下挂 models），也**没有** classifier（决策模型）与生图模型的可用路径：`output_modalities` 含 `decision` 的模型与纯图/视频/音频输出模型一律不写入。
