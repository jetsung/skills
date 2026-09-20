# opencode 配置参考（`~/.config/opencode/opencode.json`）

官方文档：https://opencode.ai/docs/models 、https://opencode.ai/docs/providers

## 读取与写入格式

`provider.{渠道}.models` 是**对象（map）**，key 为 `{family}/{id}` 或 `{id}`，value 为 `{id, name, family}`：

```json
"openrouter/stealth-ox-alpha-free": {
  "id": "stealth-ox-alpha-free",
  "name": "openrouter/stealth-ox-alpha-free",
  "family": "openrouter"
}
```

> opencode 的模型 key/name 通常复用渠道中的完整模型 id，具体以 opencode.json 现有 provider 的 models 结构为准（可能为 0 条，需参考同文件的 other provider 结构）。

## 配置结构（官方文档摘录）

- 配置文件 `~/.config/opencode/opencode.json`（支持 JSONC），`$schema: "https://opencode.ai/config.json"`；内置 75+ 提供商（经 AI SDK + [Models.dev](https://models.dev) 目录），凭据经 `/connect` 存于 `~/.local/share/opencode/auth.json`
- **模型引用格式**：完整 id 为 `provider_id/model_id`；`provider_id` 是配置中 `provider` 对象的键名，`model_id` 是 `provider.models` 的键名
- **provider 级字段**：
  - `options.baseURL`：覆盖该 provider 的端点（代理/自建网关用）
  - `models`：对象 map，key 为模型 id，value 为模型条目（`{id, name, family}`，另可含下述 options/variants）
  - `blacklist`：`[模型id]`，从 `/models` 选择器隐藏指定模型；`whitelist`：只保留列出模型；两者可组合（先 whitelist 收窄再 blacklist 剔除）
- **模型条目 `options`**（全局请求选项）：
  - OpenAI 类：`reasoningEffort`（`none`~`xhigh`）、`textVerbosity`、`reasoningSummary`、`include: ["reasoning.encrypted_content"]`
  - Anthropic 类：`thinking: { type: "enabled", budgetTokens: 16000 }`
- **`variants`（变体）**：同一模型多套配置而不建重复条目——`models.{id}.variants.{变体名}` 内放 options 同款字段；内置变体：Anthropic `high`/`max`（思考预算），OpenAI `none`/`minimal`/`low`/`medium`/`high`/`xhigh`，Google `low`/`high`；变体可设 `disabled: true` 停用；`variant_cycle` 快捷键切换
- **默认模型**：顶层 `"model": "provider_id/model_id"`；启动加载优先级：`--model` 标志 > 配置 `model` 字段 > 上次使用的模型 > 第一个可用模型

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "opencode/gpt-5.1-codex",
  "provider": {
    "openai": {
      "options": { "baseURL": "https://my-proxy.example.com/v1" },
      "blacklist": ["gpt-5-legacy"],
      "models": {
        "gpt-5": {
          "options": { "reasoningEffort": "high" },
          "variants": {
            "low": { "reasoningEffort": "low" },
            "fast": { "disabled": true }
          }
        }
      }
    }
  }
}
```

> 同步脚本只合并 `provider.{渠道}.models` map（含各条目的 options/variants），不动 `options.baseURL` 等已有渠道字段。

## 全量同步脚本

```bash
python3 scripts/sync-pi-to-opencode.py
```

目标配置：`~/.config/opencode/opencode.json`；models 格式为对象 map（key=id，value 含 family=id 前缀或渠道名）；apiKey 保留 `{env:XXX}` 占位符。幂等可重复执行，自动备份+断言校验。
