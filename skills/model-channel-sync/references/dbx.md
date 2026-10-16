# DBX 配置参考（`dbx.db` 的 `ai_configs` 表）

DBX 桌面端把 AI 模型配置存在数据目录下的 SQLite 库 `dbx.db` 的 `ai_configs` 表中。完整表结构由 AI 从本机数据库提取整理，见 `/tmp/dbx/ai-configs-schema.md`（如不存在可重新提取）。

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
    name        TEXT NOT NULL UNIQUE,        -- 配置名称
    model       TEXT NOT NULL DEFAULT '',    -- 当前选中模型（冗余列，与 config_json.model 双写一致）
    models      TEXT NOT NULL DEFAULT '[]',  -- 已保存模型列表（JSON 数组字符串，与 config_json.models 双写一致，数组元素为 {id, name} 对象）
    config_json TEXT NOT NULL,               -- 完整配置（JSON 字符串，真正 schema 在这里）
    is_default  INTEGER NOT NULL DEFAULT 0   -- 默认配置标记，全局最多 1 个（部分唯一索引）
);
CREATE UNIQUE INDEX idx_ai_configs_default ON ai_configs(is_default) WHERE is_default = 1;
```

> **双写约束（重要）**：DBX 同时使用顶层列 `model`/`models` 与 `config_json.model`/`config_json.models`。新版 DBX 在 UI 读取时以 `config_json` 为主，但列表/搜索可能读顶层列，**写入时必须双写保持一致**：`model` 列 = `config_json.model`，`models` 列 = `JSON.stringify(config_json.models)`。只写一处会导致模型列表在 DBX 界面显示为空。
> **models 格式（重要）**：新版 DBX 的 `models` 元素为**对象** `{id, name}`（如 `{"id":"deepseek-flash","name":"Sense DeepSeek Flash"}`），旧版 `["string1","string2"]` 字符串数组已不再兼容，迁移时会报 `invalid type: string "...", expected struct AiModelListItem` 并阻塞启动；`name` 缺失会报 `missing field 'name'`。同步脚本已兼容旧格式读取，但写入一律为对象数组。

## config_json 字段说明

真正的 schema 在 `config_json` JSON 列里。

| 字段 | 类型 | 示例值 | 说明 |
| --- | --- | --- | --- |
| `provider` | string | `"openai-compatible"` | 供应商预设：claude / openai / gemini / deepseek / qwen / minimax / ollama / openai-compatible / anthropic-compatible / custom（**新版 DBX 新建配置默认为 `openai-compatible`**，旧版 `custom` 仍兼容；同步时 `openai-completions`/`openai-responses` → `openai-compatible`，`anthropic-messages` → `anthropic-compatible`，自动迁移） |
| `apiKey` | string | （明文存储，敏感） | API Key，**未加密**，直接存在 JSON 里 |
| `authMethod` | string | `"bearer"` | 认证方式 |
| `endpoint` | string | `https://token.sensenova.cn/v1` | API 端点 |
| `model` | string | `"sensenova-6.8-flash-lite"` | 当前模型（与顶层 `model` 列**双写一致**） |
| `models` | array | `[{"id":"deepseek-flash","name":"Sense DeepSeek Flash"}]` | 手动保存的模型列表（**对象数组** `{id, name}`，与顶层 `models` 列**双写一致**，JSON 数组字符串；旧 `string[]` 已废弃） |
| `apiStyle` | string | `"completions"` | API 风格：completions / responses / anthropic-messages |
| `customHeaders` | object | `{}` | 自定义 HTTP 请求头（值敏感） |
| `proxyEnabled` / `proxyUrl` | bool / string | `false` / `""` | 代理设置 |
| `skipTlsVerify` | bool | `false` | 跳过 TLS 校验 |
| `enableThinking` | bool | `true` | 是否开启 thinking |
| `reasoningLevel` | string | `"default"` | 推理强度 |
| `maxOutputTokens` | number\|null | `null` | 最大输出 token |
| `contextWindow` | number\|null | `null` | 上下文窗口 |
| `maxRetries` | number\|null | `null` | API 重试次数（默认 2，范围 0–10） |
| `{codex,claudeCode,piAgent,opencode,cursor,grok,codebuddy,qoder}CliPath` | string\|null | `null` | 本地 CLI Agent 可执行文件路径 |
| 同名 `CliEnv` | object | `{}` | 本地 CLI Agent 额外环境变量 |

## 写入规则（sync-pi-to-dbx.py）

- **渠道匹配**：已有配置按 `config_json.endpoint`（baseUrl 去尾斜杠）优先匹配，其次 `name`（渠道显示名）；无匹配则新建（`id=uuid4`，`name=渠道显示名`）
- **模型筛选**：openrouter 渠道只补免费模型（id 含 `:free`/`-free`/`/free`），其它渠道全量同步；kilo/openrouter 从上游 API 提取免费模型（`fetch_free.py`）；opencode 不同步
- **模型 id**：保持 pi 原样，不擅自添加/去前缀；`name` 取 pi 的 `model.name`（缺失则回退 `id`）
- **model 选取**：同族最高版本（族键 = 最后一段的开头连续字母，版本号 = 首个数字串，与其它 sync 脚本一致；`best` 取 pi 原序首族，避免排序错族）
- **models 列表**：合并式（只增不删），已有条目不动；**对象数组** `{id, name}`，写入时**双写**顶层 `models` 列与 `config_json.models`；兼容旧 `string[]` 读取并自动迁移为对象数组
- **字段映射**：pi `api` → `apiStyle`（openai-completions→completions、openai-responses→responses、anthropic-messages→anthropic-messages）；`api` → `provider`（openai-*→openai-compatible、anthropic-messages→anthropic-compatible）；`baseUrl` → `endpoint`（去尾斜杠）；`apiKey` env 占位符解析为**明文实值**写入
- **provider 迁移**：已有记录 `provider=custom` 自动迁移为 `openai-compatible`/`anthropic-compatible`
- **只动这些字段**：`model` / `apiKey` / `endpoint` / `apiStyle` / `provider` / `models` / `name`（新建时初始化完整结构）；已有记录的 `customHeaders`、代理、推理强度、CLI 路径等字段**不更新**
- **is_default 不改动**；新建记录写 0，默认配置由用户在 DBX 设置中手动指定
- **写库前备份** `dbx.db.bak-YYYYMMDD`，写库后断言校验（行数只增不减、已有行 `id`/`is_default` 不变）
- **密钥不回显**：报告只写长度/变化状态，绝不输出 apiKey 内容

## 操作注意

- 写库前先退出 DBX 应用（避免 SQLite 写锁与运行时覆盖）；只读查看可直接 `sqlite3 dbx.db`
- 直接打开数据库查看：`sqlite3 <数据目录>/dbx.db "SELECT name, model, is_default FROM ai_configs"`
- 双写校验：`python3 -c "import sqlite3,json;con=sqlite3.connect('dbx.db');[print(r[0], r[1]==json.loads(r[3])['model'], json.loads(r[2])==json.loads(r[3])['models']) for r in con.execute('SELECT name,model,models,config_json FROM ai_configs')]"`
- 排查启动阻塞：`tail -f ~/.local/share/com.dbx.app/database-backups/worker.log | grep -E "invalid ai_configs|missing field"` — `string "..." expected struct AiModelListItem` 表示 `models` 仍为字符串数组，`missing field 'name'` 表示对象缺 `name`
- dbx.db 是敏感文件（含明文 apiKey），切勿提交到版本库或外发
