# zcode 配置参考（`~/.zcode/v2/provider_config.json`）

zcode 配置为**规则式**结构，顶层 `{schemaVersion: 1, config}`：

```json
{
  "schemaVersion": 1,
  "config": {
    "providerOrder": ["new-provider", "tokenrouter", "builtin:zai"],
    "providerConfigRules": {
      "providerRules": [
        {
          "providerId": "tokenrouter",
          "providerName": "TokenRouter",
          "config": {
            "group": "standard-personal",
            "access": {
              "type": "api-key",
              "apiKey": "sk-xxx"
            },
            "api": {
              "type": "openai-chat-completions",
              "baseUrl": "https://api.tokenrouter.com/v1"
            },
            "personalModelIds": ["z-ai/glm-5.3-free"],
            "modelOrder": ["z-ai/glm-5.3-free"]
          }
        }
      ]
    },
    "modelConfigRules": {
      "providerModelRules": [
        {
          "modelId": "z-ai/glm-5.3-free",
          "config": { "enabled": true },
          "providerId": "tokenrouter"
        }
      ],
      "manualProviderModelRules": []
    }
  }
}
```

## schema 要点（严格约束，写入时不可违反；源自解包 zcode 0.16.9 运行时 zod schema 与内置 `zcode-builtin.json`）

- **providerId**：内置渠道为 `builtin:xxx`；自定义渠道为 **baseURL 域名主体**（去掉子域名与顶级后缀；多段顶级后缀如 `com.cn` 取 3 段中的主体，如 `developer.amd.com.cn` → `amd`；`{env:VAR}` 占位符无法解析域名时保留渠道原名）。**同主体不同 TLD 消歧**：不同域名提取出相同主体时（如 `api.agnes-ai.cn` 与 `api.agnes-ai.com` 均为 `agnes-ai`），命名**确定性带顶级后缀**——`agnes-ai-cn` 与 `agnes-ai-com`（`.` → `-`），与处理顺序无关，保证幂等；**禁止**用 `-2`/`-3` 序号后缀消歧（顺序依赖，重跑可能互换导致重复创建）。单一渠道时维持简洁主体（`tokenrouter`）。同一 `provider_config.json` 内不可重复
- **渠道条目**：`{providerId, providerName, config}`，`config` 字段集合**固定**为 `group`（`standard-personal`）、`access: {type: "api-key", apiKey}`、`api: {type, baseUrl}`、`personalModelIds[]`、`modelOrder[]`——**不可添加任何额外字段**（无 enabled/source/kind/models），字段顺序为 `group → access → api → personalModelIds → modelOrder`
- **api.type 映射**：pi 的 `openai-completions` → `openai-chat-completions`；pi 的 `anthropic` → `anthropic-messages`
- **模型条目**：`{modelId, config: {enabled: true}, providerId}`——`config` **只有 `enabled: true`**，不写 properties/optionSpecs/displayName 等
- **新增渠道时**：`providerRules` 追加条目、`providerOrder` 追加 ID、每个模型追加一条 `providerModelRules`；`personalModelIds` 与 `modelOrder` 内容相同（模型 id 顺序一致）
- **只合并模型时**：向目标渠道的 `personalModelIds`/`modelOrder` 追加新模型 id（两处都加），并向 `providerModelRules` 追加对应条目；已有条目一律不动

## 完整 schema 枚举值（zod 严格模式，超出枚举即校验失败；个人渠道用不到的枚举仅作识别参考，勿写入）

| 字段路径 | 类型/枚举 |
|----------|-----------|
| `providerConfigRules` | `{templateRules[], providerRules[]}` 两个数组 |
| `providerRules[].config.group` | enum：`standard-personal`（个人渠道唯一可用值）/ `zai-family` / `bigmodel-family`（内置专用） |
| `providerRules[].config.access` | discriminatedUnion(type)：`api-key`（`{type, apiKey, apiKeyManagementUrl?}`）/ `zhipu-coding-plan-api-key`（`{type, apiKey?, apiKeyManagementUrl?}`）/ `zhipu-account`（`{type, accountType: zai\|bigmodel, mode: start-plan\|individual-coding-plan\|team-coding-plan\|off-peak, entitled}`，内置专用） |
| `providerRules[].config.api` | `{type, baseUrl, headers?}`，`headers` 为 string map（值同样不支持 env 插值）；`type` enum：`anthropic-messages` / `openai-chat-completions` / `openai-responses` |
| `providerRules[].config` 可选字段 | `logo?: {type: "builtin", key: string}`、`visibility?: "visible"|"hidden"`、`builtinModelIds?[]`、`enabled?`——个人自定义渠道**不写**这些 |
| `modelConfigRules` | `{modelRules[], modelApiRules[], providerSiteRules[], templateModelRules[], builtinProviderModelRules[], providerModelRules[], manualProviderModelRules[]}`；个人渠道只写 `providerModelRules` |
| `modelRules[]` / 其它模型规则 | `{modelMatch: 正则, config, apiTypeMatch?/baseUrlMatch?}`——按正则批量匹配内置模型；`templateModelRules`：`{templateId, modelId, config}`；`builtinProviderModelRules`/`providerModelRules`：`{modelId, config, providerId}`（`config` 可含 `enabled?/properties?/optionSpecs?`） |
| 模型 `config.properties` | 可选对象：`contextWindow`（正整数）、`inputFormat: {supportsText, supportsImage, supportsVideo, supportsAudio, supportsPdf}`、`outputFormat: {supportsText}`、`supportsToolCall`、`supportsJsonSchemaOutput`、`supportsNativeWebSearch`、`supportsMidConversationSystem`、`requiresMfjsToolSchema`（均 boolean） |
| 模型 `config.optionSpecs` | 可选对象：`reasoningLevel: {values: string[]（非空，如 ["disabled","enabled","low","high","max"]）}`、`maxOutputTokens: {max: 正整数}` |
| `apiKeyManagementUrl` | 可选，必须是合法 URL（如 `https://z.ai/manage-apikey/apikey-list`） |

> zcode 的 `access.apiKey` **只支持明文实值，不支持任何环境变量形式**（已解包 zcode 0.16.9 运行时验证：`resolveApiKey` 为恒等透传，`{env:VAR}`、`!echo -n "$VAR"`、`${VAR}`、dotenvx `.env` 均无解析逻辑，占位符会被当字面文本原样发送导致鉴权失败；`api.headers` 的值同样不做 env 插值）。读取时直接取值，注意勿将密钥写入日志/输出；同步脚本从 pi 的 `!echo -n "$VAR"` 解析 env 后注入明文。写入后**必须校验**：渠道与模型条目的字段集合与文件中现有条目完全一致（多余的 `enabled`/`properties` 等字段会导致格式错误）。

## 读取渠道配置

结构为 `config.providerConfigRules.providerRules[]`（规则数组，每条 `{providerId, providerName, config}`）。渠道 key（`providerId`）为 `builtin:xxx`（内置渠道）或域名主体（自定义渠道，即 baseURL 域名去掉子域名与顶级后缀，如 `https://api.tokenrouter.com/v1` → `tokenrouter`、`https://developer.amd.com.cn/...` → `amd`；同主体不同 TLD 时带顶级后缀消歧，如 `agnes-ai-cn`/`agnes-ai-com`）。渠道 `config` 字段固定为 `group`（`standard-personal`）、`access: {type: "api-key", apiKey}`（**明文 key**）、`api: {type: "anthropic-messages"|"openai-chat-completions", baseUrl}`、`personalModelIds[]`、`modelOrder[]`。模型列表在 `config.modelConfigRules.providerModelRules[]`，不在渠道内：

```bash
# 示例：zcode 的 OpenRouter（providerId 为域名主体）
python3 -c "
import json
c = json.load(open('$HOME/.zcode/v2/provider_config.json'))['config']
r = next(r for r in c['providerConfigRules']['providerRules'] if r['providerName'] == 'OpenRouter')
print('PROVIDER_ID:', r['providerId'])
print('BASE_URL:', r['config']['api']['baseUrl'])
print('API_KEY:', r['config']['access']['apiKey'])
print('API_TYPE:', r['config']['api']['type'])
print('MODELS:', r['config']['personalModelIds'])
"
```

> 注意：zcode 的 `api.type` 为 `anthropic-messages` 的渠道通常不支持 `GET {baseUrl}/models`（Anthropic 协议无此端点），此时直接从该渠道 `personalModelIds` 读取模型列表，并告知用户改用配置读取方式。

## 渠道匹配方法（pi → zcode）

zcode 的渠道 key（`providerId`）是域名主体/`builtin:xxx`，与 pi 的渠道名不同，需按 `providerName` 字段匹配。匹配前先规范化（小写并去除非字母数字）再比较；规范化后仍不一致的用显式别名（如 pi 的 `cloudflare-workers-ai` 规范化后是 `cloudflareworkersai`，zcode 的 `CloudFlare AI` 规范化后是 `cloudflareai`，需手动映射）。pi 的 `apiKey` 形如 `!echo -n "$ENV_VAR"`，提取环境变量名时正则须含数字：`r'!echo -n "\$([A-Z0-9_]+)"'`（变量名可能是 `DS2API_API_KEY`、`V2EX_API_KEY` 这类含数字的形式）。

## 全量同步（以 pi 为基准：provider + models + apiKey）

用户要求"以 pi 的渠道/模型为基准更新 zcode"时，直接运行技能自带脚本（幂等可重复执行；只改目标字段；密钥不回显）：

```bash
python3 scripts/sync-pi-to-zcode.py
```

脚本位置：`scripts/sync-pi-to-zcode.py`（相对技能目录）。执行前按需修改脚本顶部 `PI_PATH`/`ZC_PATH`/`ALIAS` 三个变量。

**脚本行为：**
- 备份（`.bak-YYYYMMDD`）→ 匹配渠道（按 `providerName` 规范化+别名映射）→ 合并 models（`personalModelIds`/`modelOrder` 追加缺失 + `providerModelRules` 补 `{modelId, config:{enabled:true}, providerId}`，幂等）→ 更新 apiKey（env 解析，正则含数字）→ 写回（不转义中文）→ 断言校验（渠道/模型条目字段集合与现有条目完全一致，只允许 models 新增与 apiKey 变化）
- 无对应渠道时按 schema 自动创建（providerId = baseURL 域名主体，同主体不同 TLD 时带顶级后缀消歧如 `agnes-ai-cn`，禁用序号后缀；字段集合固定，无额外字段）
- 输出即报告摘要：渠道名 / env 名 / 长度 / 变化状态，不含密钥内容

**要点：**
- 渠道名匹配用规范化+显式别名（如 `cloudflare-workers-ai` → `CloudFlare AI`），不能直接字符串比较
- 明文 apiKey 绝不打印；多轮执行幂等，不会重复添加
- 长脚本用 heredoc/独立脚本文件传给 python3，**不要用 bash 双引号 `-c "..."`**（会吞掉 `\$`/`\"` 转义导致正则失效）
