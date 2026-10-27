# opencode 配置参考（v2 原生格式，`~/.config/opencode/opencode.json`）

官方文档：https://opencode.ai/v2/docs/models 、https://opencode.ai/v2/docs/providers 、https://opencode.ai/v2/docs/migrate-v1

> opencode v2 仍读取 `~/.config/opencode/opencode.json(c)`，`$schema: "https://opencode.ai/config.json"` 不变；
> V1 格式仍被兼容（内存中自动归一化），但原生 v2 格式为推荐写法（2026-10 已全量迁移）。

## 读取与写入格式

顶层键为 **`providers`**（V1 为 `provider`）。`providers.{渠道}.models` 是**对象（map）**，key 为 `{family}/{id}` 或 `{id}`，value 为：

```json
"openrouter/stealth-ox-alpha-free": {
  "modelID": "stealth-ox-alpha-free",
  "name": "openrouter/stealth-ox-alpha-free",
  "family": "openrouter"
}
```

> 模型条目 V1 的 `id` 字段在 v2 改名 **`modelID`**（发给上游的真实模型 id）；key/name 通常复用渠道中的完整模型 id，具体以 opencode.json 现有 provider 的 models 结构为准（可能为 0 条，需参考同文件的 other provider 结构）。

## 配置结构（官方文档摘录）

- 凭据经 `/connect` 存于 `~/.local/share/opencode/auth.json`
- **模型引用格式**：`provider_id/model_id`（可带 `#variant` 变体）；`provider_id` 是 `providers` 对象的键名，`model_id` 是 `provider.models` 的键名
- **provider 级字段**（V1 → V2 改名）：
  - `npm` → **`package`**：适配器包名；AI SDK 包需加 `aisdk:` 前缀，OpenAI 兼容端点用 `aisdk:@ai-sdk/openai-compatible`。同步脚本对缺失/为空的 provider 兜底补该值（插在 `settings` 之前），已有值不动
  - `options` → **`settings`**：provider 包选项（`apiKey`、`baseURL` 等都放这里）；另有 `headers`（额外请求头）与 `body`（请求体字段）分离
  - `api` 字段废弃，端点改用 `settings.baseURL`
  - `models`：对象 map，key 为模型 id，value 为模型条目（`{modelID, name, family}`，另可含 capabilities/limit/variants）
  - V1 `blacklist`/`whitelist` 无原生字段，行为经 `policies` 实现（可继续保留 V1 写法，自动归一化）
- **模型条目**：
  - `id` → `modelID`；`tool_call`/`modalities` → `capabilities.tools`/`capabilities.input`/`capabilities.output`；`status: "deprecated"` → `disabled: true`；缓存成本 `cache_read`/`cache_write` → `cache.read`/`cache.write`
  - 请求选项 `options` → `settings`（如 OpenAI 类 `reasoningEffort`、Anthropic 类 `thinking`），模型级 `body` 放 provider 特定请求体字段
  - `compatibility.reasoningField` 可指定流式推理字段（识别 `reasoning`/`reasoning_content`/`reasoning_text`）
- **`variants`（变体）**：V1 对象改为**数组**，每项带 `id`：

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
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

- **默认模型**：顶层 `"model": "provider_id/model_id"` 不变；选择优先级：会话已选 > `--model` 标志 > 配置 `model` 字段 > 最新可用模型
- **其他 v2 顶层改名**：`plugin` → `plugins`、`agent` → `agents`、`command` → `commands`、`mcp` 下服务器归入 `mcp.servers`（`enabled` 反转为 `disabled`）、`attachment` → `media`、`snapshot` → `snapshots`、`skills.paths+urls` 合并为数组

> 同步脚本只合并 `providers.{渠道}.models` map（含各条目的 settings/variants）与补全缺失的 `package`，不动 `settings.baseURL` 等已有渠道字段。

## 全量同步脚本

```bash
python3 scripts/sync-pi-to-opencode.py
```

目标配置：`~/.config/opencode/opencode.json`；models 格式为对象 map（key=id，value 含 modelID/family=id 前缀或渠道名）；apiKey 保留 `{env:XXX}` 占位符。幂等可重复执行，自动备份+断言校验。
