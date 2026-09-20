# pi 配置参考（`~/.pi/agent/models.json`）

pi 的模型配置文件位于 `~/.pi/agent/models.json`，结构为 `providers.{渠道}.models` 数组。完整文档见 [pi.dev/docs/latest/models](https://pi.dev/docs/latest/models)（源文件：pi 仓库 `packages/coding-agent/docs/models.md`）。

**写入范围（重要）**：本技能只写**用户级（全局）** `~/.pi/agent/models.json`，**禁止修改项目级**模型配置（如 `<workspace>/.pi/agent/models.json` 等项目内路径）——所有同步目标工具同理，一律只写用户级全局配置，不写项目仓库内的任何配置文件。

## 读取渠道配置

从 `~/.pi/agent/models.json` 读取目标渠道的 `baseUrl` 和 `apiKey`。注意 `apiKey` 形如 `!echo -n "$ENV_VAR"`，需解析出环境变量名并取值：

```bash
# 示例：openrouter
BASE_URL="https://openrouter.ai/api/v1"
API_KEY="$OPENROUTER_API_KEY"
```

## 支持的 API 类型（`api` 字段）

| 值 | 说明 |
|----|------|
| `openai-completions` | OpenAI Chat Completions（最通用，默认常用） |
| `openai-responses` | OpenAI Responses API |
| `anthropic-messages` | Anthropic Messages API |
| `google-generative-ai` | Google Generative AI（自定义模型时 `baseUrl` 必填，如 `https://generativelanguage.googleapis.com/v1beta`） |

`api` 可设在 provider 级（对该渠道所有模型生效）或 model 级（覆盖单个模型）。

## Provider 字段

| 字段 | 说明 |
|------|------|
| `baseUrl` | API 端点 URL |
| `api` | API 类型（见上表） |
| `apiKey` | 可选；auth 也可由 `/login`/`auth.json` 或 CLI `--api-key` 提供，此时省略。未配置 auth 时模型仍加载但在 `/model` 中不可用 |
| `oauth` | 动态 OAuth 供应商类型（当前支持 `"radius"`，需网关 `baseUrl`） |
| `headers` | 自定义请求头（支持值解析，见下） |
| `authHeader` | 设 `true` 自动添加 `Authorization: Bearer <apiKey>` |
| `models` | 模型配置数组 |
| `modelOverrides` | 对内置/扩展注册模型的逐模型覆盖（见下） |
| `compat` | provider 级兼容性覆盖，对该渠道所有模型生效 |

## 值解析（Value Resolution，`apiKey` 与 `headers` 通用）

- **Shell 命令**：值以 `!command` 开头时执行整个命令并取 stdout，如 `"!security find-generic-password -ws 'anthropic'"`、`"!echo -n \"$ENV_VAR\""`；`models.json` 中命令在**请求时**解析，pi 不做 TTL/失败重用
- **环境变量插值**：`"$ENV_VAR"` 或 `"${ENV_VAR}"`，可嵌在更大字面量中（`"${KEY_PREFIX}_${KEY_SUFFIX}"`）；`$FOO_BAR` 取变量 `FOO_BAR`，`BAR` 是字面文本时用 `${FOO}_BAR`；变量不存在则值未解析
- **转义**：`"$$"` 输出字面 `$`；`"$!"` 输出字面 `!`（不触发命令执行）
- **字面量**：直接使用（`"sk-..."`）；纯大写字符串如 `MY_API_KEY` 是字面量，环境变量须带 `$` 前缀
- `/model` 的可用性检查只看已配置的 auth，**不执行** shell 命令

## Model 字段

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | 是 | — | 模型标识符，传递给 API |
| `name` | 否 | `id` | 可读标签，用于匹配（`--model` 模式）与次级详情文本；页脚/状态栏仍显示 `id` |
| `api` | 否 | 继承 provider 的 `api` | 覆盖 provider 的 API 类型 |
| `reasoning` | 否 | `false` | 是否支持扩展思考 |
| `thinkingLevelMap` | 否 | 省略 | 映射 pi 思考级别（`off`/`minimal`/`low`/`medium`/`high`/`xhigh`/`max`）到 provider 值；值为 string（发送该值）、`null`（该级别不支持，UI 隐藏）或省略（默认映射）；允许空洞 |
| `input` | 否 | `["text"]` | 输入类型：`["text"]` 或 `["text", "image"]` |
| `contextWindow` | 否 | `128000` | 上下文窗口大小（token） |
| `maxTokens` | 否 | `16384` | 最大输出 token 数 |
| `samplingParams` | 否 | 省略 | 自由对象，逐字段合并进每个请求体（键优先于 pi 自设字段）；仅 OpenAI 兼容 API（`openai-completions`/`openai-responses`/`azure-openai-responses`）生效，其它 API 忽略 |
| `cost` | 否 | 全零 | 每百万 token 计费 `{input, output, cacheRead, cacheWrite}`，可含 `tiers`（`inputTokensAbove` 阈值费率，多档命中取最高阈值） |
| `compat` | 否 | 继承 provider 的 `compat` | 兼容性覆盖，与 provider 级合并（模型级优先） |

`cost.tiers` 示例：
```json
{
  "cost": {
    "input": 5, "output": 30, "cacheRead": 0.5, "cacheWrite": 6.25,
    "tiers": [{ "inputTokensAbove": 272000, "input": 10, "output": 45, "cacheRead": 1, "cacheWrite": 12.5 }]
  }
}
```

## Full Example

```json
{
  "providers": {
    "ollama": {
      "baseUrl": "http://localhost:11434/v1",
      "api": "openai-completions",
      "apiKey": "ollama",
      "models": [
        {
          "id": "llama3.1:8b",
          "name": "Llama 3.1 8B (Local)",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 128000,
          "maxTokens": 32000,
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 }
        }
      ]
    }
  }
}
```

## 覆盖内置 provider 与 modelOverrides

- **只改端点**：内置 provider（如 `anthropic`）可只写 `baseUrl` 走代理，内置模型全部保留，已有 OAuth/API key 继续生效
- **合并自定义模型**：内置 provider 带 `models` 数组时，自定义模型按 `id` upsert——同 `id` 替换内置条目，新 `id` 追加，内置模型保留
- **modelOverrides**：不替换整个 models 列表，逐模型覆盖内置/扩展注册模型；支持字段：`name`、`reasoning`、`thinkingLevelMap`、`input`、`cost`（可部分）、`contextWindow`、`maxTokens`、`samplingParams`（逐键合并）、`headers`、`compat`；未知 id 忽略；与 `models` 同时存在时自定义模型合并在覆盖之后（同 `id` 自定义条目胜出）
```json
{
  "providers": {
    "openrouter": {
      "modelOverrides": {
        "anthropic/claude-sonnet-4": {
          "name": "Claude Sonnet 4 (Bedrock Route)",
          "compat": { "openRouterRouting": { "only": ["amazon-bedrock"] } }
        }
      }
    }
  }
}
```

## compat 常用字段（按 API 类型）

**OpenAI 兼容（openai-completions / openai-responses）**：`supportsStore`、`supportsDeveloperRole`（`developer` vs `system` 角色，本地服务常设 `false`）、`supportsReasoningEffort`、`supportsUsageInStreaming`、`supportsFinishReason`、`maxTokensField`（`max_completion_tokens` 或 `max_tokens`）、`requiresToolResultName`、`requiresAssistantAfterToolResult`、`requiresThinkingAsText`、`requiresReasoningContentOnAssistantMessages`、`thinkingFormat`（`reasoning_effort`/`openrouter`/`deepseek`/`together`/`baseten`/`zai`/`qwen`/`chat-template`/`qwen-chat-template`）、`chatTemplateKwargs`/`chatTemplateArgs`、`thinkingTokenBudgetField`（`thinking_token_budget`=vLLM、`thinking_budget`=Qwen/DashScope/SGLang、`thinking_budget_tokens`=llama.cpp）、`cacheControlFormat: "anthropic"`、`supportsStrictMode`、`supportsOpenAIGrammarTools`、`supportsLongCacheRetention`、`openRouterRouting`（原样发送到 OpenRouter 请求的 `provider` 字段）、`vercelGatewayRouting`（`only`/`order`）

**Anthropic Messages（anthropic-messages）**：`supportsEagerToolInputStreaming`（默认 `true`，代理拒绝时设 `false`）、`supportsLongCacheRetention`、`supportsCacheControlOnTools`、`forceAdaptiveThinking`（自适应思考 `thinking.type: "adaptive"`）、`supportsMidConvoEffort`、`allowEmptySignature`（仅对回放空签名 thinking 块的供应商设 `true`，真 Anthropic 拒绝空签名）、`supportsStrictTools`、`allowedFallbackModels`（最多 3 个服务端回退模型，需完整 `cost` 元数据；空数组禁用回退）

```json
{
  "providers": {
    "local-llm": {
      "baseUrl": "http://localhost:8080/v1",
      "api": "openai-completions",
      "compat": { "supportsDeveloperRole": false, "supportsReasoningEffort": false },
      "models": [{ "id": "gpt-oss:20b", "reasoning": true }]
    }
  }
}
```

## 写入 pi 时的字段映射

`providers.{渠道}.models` 是**数组**，元素为 `{id, name}`；若 API 返回了 `maxTokens`、`contextWindow`、`reasoning`、`input`、`cost` 等字段，一并写入：

```json
{
  "id": "stealth/ox-alpha",
  "name": "Stealth OX Alpha (Free)",
  "maxTokens": 4096,
  "contextWindow": 128000
}
```

**字段映射（API 响应 → pi models.json）**：

| API 字段 | pi 字段 | 说明 |
|----------|---------|------|
| `id` | `id` | 模型标识符 |
| `name` | `name` | 可读标签 |
| `max_tokens` / `maxTokens` | `maxTokens` | 最大输出 token 数 |
| `context_length` / `contextWindow` | `contextWindow` | 上下文窗口大小 |
| `reasoning` | `reasoning` | 是否支持推理 |
| `input` | `input` | 输入类型，如 `["text"]` 或 `["text","image"]` |
| `cost` | `cost` | 计费信息 `{input, output, cacheRead, cacheWrite}` |

写入时以 pi 现有配置结构为准，仅合并/新增模型条目，保留已有条目不变。文件每次打开 `/model` 时自动重载，编辑后无需重启。
