# opencode 配置参考（v2 原生格式，`~/.config/opencode/opencode.json`）

opencode v2 仍读取 `~/.config/opencode/opencode.json(c)`，`$schema: "https://opencode.ai/config.json"` 不变；V1 格式仍被兼容（内存中自动归一化），但原生 v2 格式为推荐写法。官方文档：<https://opencode.ai/v2/docs/models>、<https://opencode.ai/v2/docs/providers>、<https://opencode.ai/v2/docs/migrate-v1>。多平台同步的完整说明见 `model-channel-sync` 技能的 `references/opencode.md`。

**写入范围**：只写用户级 `~/.config/opencode/opencode.json`，禁止修改项目级配置。

**渠道新增约束**：本技能第 7 步守卫把 `opencode` 与 `openrouter` 列为默认禁止新增渠道——未经用户显式声明（`ALLOW_NO_AUTO_ADD=1` 或渠道列表）不得新建，仅允许更新已存在的渠道（详见 SKILL「渠道新增约束检查」）。

## 读取与写入格式

顶层键为 **`providers`**（V1 为 `provider`）。`providers.{渠道}.models` 是**对象（map）**——既不是 pi/omp 的数组，也不是 DBX 的对象数组：key 为 `{family}/{id}` 或 `{id}`，value 为模型条目：

```json
"openrouter/stealth-ox-alpha-free": {
  "modelID": "stealth-ox-alpha-free",
  "name": "openrouter/stealth-ox-alpha-free",
  "family": "openrouter"
}
```

> 模型条目 V1 的 `id` 字段在 v2 改名 **`modelID`**（发给上游的真实模型 id）；key/name 通常复用渠道中的完整模型 id，具体以 opencode.json 现有 provider 的 models 结构为准（可能为 0 条，需参考同文件其他 provider 的结构）。

- **模型引用格式**：`provider_id/model_id`（可带 `#variant` 变体）；`provider_id` 是 `providers` 的键名，`model_id` 是 `provider.models` 的键名
- **默认模型**：顶层 `"model": "provider_id/model_id"`；选择优先级为 会话已选 > `--model` 标志 > 配置 `model` 字段 > 最新可用模型
- **凭据**：官方经 `/connect` 存于 `~/.local/share/opencode/auth.json`；配置文件内则用 `settings.apiKey`（可写 `{env:VAR}` 占位符）

## 渠道（provider）字段

V1 → V2 改名对照：

| V2 字段 | V1 字段 | 说明 |
|---------|---------|------|
| `package` | `npm` | 适配器包名；AI SDK 包需加 `aisdk:` 前缀，OpenAI 兼容端点用 `aisdk:@ai-sdk/openai-compatible`。缺失/为空时补该值（插在 `settings` 之前），已有值不动 |
| `settings` | `options` | provider 包选项（`apiKey`、`baseURL` 等都放这里）；另有 `headers`（额外请求头）与 `body`（请求体字段）分离 |
| `settings.baseURL` | `api`（已废弃） | 端点地址不再写 `api` 字段，改用 `settings.baseURL` |
| `models` | `models` | 对象 map，key 为模型 id，value 为模型条目（`{modelID, name, family}`，另可含 `capabilities`/`limit`/`variants`） |
| `policies` | `blacklist`/`whitelist` | V1 黑白名单无原生字段，行为经 `policies` 实现（可继续保留 V1 写法，自动归一化） |

其他 v2 顶层改名（与模型同步无关，遇到时按此对照）：`plugin` → `plugins`、`agent` → `agents`、`command` → `commands`、`mcp` 下服务器归入 `mcp.servers`（`enabled` 反转为 `disabled`）、`attachment` → `media`、`snapshot` → `snapshots`、`skills.paths+urls` 合并为数组。

## 模型（models 的 map 值）字段

| 字段 | V1 对应 | 说明 |
|------|---------|------|
| `modelID` | `id` | 发给上游的真实模型 id，原样保留（不加/去前缀） |
| `name` | `name` | 显示名 |
| `family` | — | 模型族（用于 key 的 `{family}/{id}` 形式或渠道名） |
| `capabilities.tools` | `tool_call` | 是否支持工具调用 |
| `capabilities.input` / `capabilities.output` | `modalities` | 输入/输出模态 |
| `disabled` | `status: "deprecated"` | 禁用该模型 |
| `cache.read` / `cache.write` | `cache_read` / `cache_write` | 缓存成本 |
| `limit` | `limit` | 上下文/输出上限；目标文件已有条目使用何种子字段即沿用，上游无可靠数据则省略 |
| `settings` | `options` | 模型级请求选项（如 OpenAI 类 `reasoningEffort`、Anthropic 类 `thinking`） |
| `body` | — | 模型级 provider 特定请求体字段 |
| `variants` | 对象 → **数组** | 每项带 `id`；如 `{ "id": "low", "settings": { "reasoningEffort": "low" } }`、`{ "id": "fast", "disabled": true }` |
| `compatibility.reasoningField` | — | 指定流式推理字段（识别 `reasoning`/`reasoning_content`/`reasoning_text`） |

## 字段映射（上游 `/models` → opencode）

| 上游/输入 | opencode 字段 | 说明 |
|-----------|---------------|------|
| `<PREFIX>_BASE_URL` 实值 | `providers.{渠道}.settings.baseURL` | 真实地址；`api` 字段已废弃，勿写 |
| `<PREFIX>_API_KEY` | `providers.{渠道}.settings.apiKey` | 写 `{env:<PREFIX>_API_KEY}` 占位符，配置中不落明文 |
| 渠道标识 `channel` | `providers` 的键名 | 即模型引用中的 `provider_id` |
| 接口类型 | `providers.{渠道}.package` | OpenAI 兼容用 `aisdk:@ai-sdk/openai-compatible` |
| `id` | `models` 的 map key 与 `modelID` | key 形态（`{family}/{id}` 或 `{id}`）沿用该 provider 已有条目；`modelID` 保持上游原样 |
| `name` / `display_name` | `models.{key}.name` | 缺失时按 SKILL 的显示名规则 `{渠道显示名} - {模型名}` 生成 |
| `output_modalities` 含 `image` | `capabilities.input` | 仅上游明确提供时写入 |
| 上游无数据的可选字段 | — | 省略，不填默认值、不猜测 |

## 新增渠道示例

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "providers": {
    "sense": {
      "package": "aisdk:@ai-sdk/openai-compatible",
      "settings": {
        "baseURL": "https://token.sensenova.cn/v1",
        "apiKey": "{env:SENSE_API_KEY}"
      },
      "models": {
        "sense/sensenova-6.8-flash-lite": {
          "modelID": "sensenova-6.8-flash-lite",
          "name": "Sense Sensenova 6.8 Flash Lite",
          "family": "sense"
        }
      }
    }
  }
}
```

`baseURL` 取 `<PREFIX>_BASE_URL` 实值；`apiKey` 用 `{env:...}` 占位符形式。带变体的完整形态（源自官方文档示例）：

```jsonc
{
  "model": "opencode/gpt-5.1-codex",
  "providers": {
    "openai": {
      "package": "aisdk:@ai-sdk/openai-compatible",
      "settings": { "baseURL": "https://my-proxy.example.com/v1" },
      "models": {
        "gpt-5": {
          "modelID": "gpt-5",
          "settings": { "reasoningEffort": "high" },
          "variants": [
            { "id": "low", "settings": { "reasoningEffort": "low" } },
            { "id": "fast", "disabled": true }
          ]
        }
      }
    }
  }
}
```

## 更新已有渠道

- `providers.{渠道}.models` 按模型 id（map key 与 `modelID`）upsert：同 id 更新、新 id 追加，不产生重复；不删除本次未出现的手工模型。
- 只合并 `providers.{渠道}.models` map（含各条目的 `settings`/`variants`）并补全缺失的 `package`；**不动** `settings.baseURL`、`apiKey` 等已有渠道字段。
- 保留 `$schema`、顶层 `model` 与其他无关条目（`agents`/`plugins`/`mcp.servers` 等）原样不变。
- 若文件仍是 V1 结构（`provider` + `npm`/`options`/`id`），按上表对照处理；V1 写法仍被兼容，无需整体迁移。

## 写入后校验

```bash
python3 -m json.tool ~/.config/opencode/opencode.json > /dev/null
```

（`.jsonc` 含注释时改用 `python3 -c "import json,sys,re;json.loads(re.sub(r'^\s*//.*$','',open(sys.argv[1]).read(),flags=re.M))" <文件>` 或直接核对括号配平。）

再确认：顶层键为 `providers`、渠道存在、`package` 与 `settings.baseURL` 正确、`apiKey` 为 `{env:...}` 形式且输出中无明文、models map 的 key 唯一且 `modelID` 与本批上游 id 一致、条目数量与转换结果一致。

## 注意

- 每次真实写入前创建带时间戳备份（如 `opencode.json.bak-YYYYMMDDHHMMSS`），验证失败时用备份恢复。
- 配置文件内**不写明文密钥**（用 `{env:VAR}`）；若目标渠道原本就是明文实值，保留其形式并把文件与备份权限设为 `0600`，报告只说明"密钥已配置"。
- **决策模型（classifier）不写入**：opencode 无 classifier 注册能力，`output_modalities` 含 `decision` 的模型一律剔除（仅经 pi provider extension 使用）。
- 纯图像/视频/音频输出模型按 SKILL 第 3 步实测判定从聊天写入清单剔除，报告中注明其实际端点。
