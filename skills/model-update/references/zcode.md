# zcode 配置参考（`~/.zcode/v2/provider_config.json`）

zcode 的模型配置位于用户级文件 `~/.zcode/v2/provider_config.json`（可用环境变量 `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` 覆盖路径），结构为规则式：顶层 `{schemaVersion: 1, config}`。schema 源自 zcode 运行时 zod 严格校验（`packages/provider/src/config/`，schemaVersion 1），**超出字段枚举即校验失败**。官方源码：<https://github.com/zai-org/ZCode>。

**写入范围**：只写用户级 `provider_config.json`，禁止修改项目级配置。

## 顶层结构

```json
{
  "schemaVersion": 1,
  "config": {
    "providerOrder": ["new-provider"],
    "providerConfigRules": {
      "providerRules": [
        {
          "providerId": "new-provider",
          "providerName": "new-provider",
          "config": {
            "group": "standard-personal",
            "access": { "type": "api-key", "apiKey": "sk-xxx" },
            "api": { "type": "openai-chat-completions", "baseUrl": "https://api.example.com/v1" },
            "personalModelIds": ["model-a"],
            "modelOrder": ["model-a"]
          }
        }
      ]
    },
    "modelConfigRules": {
      "providerModelRules": [
        { "modelId": "model-a", "config": { "enabled": true }, "providerId": "new-provider" }
      ],
      "manualProviderModelRules": []
    }
  }
}
```

模型列表不在渠道内，统一在 `config.modelConfigRules.providerModelRules[]`。

## 渠道（provider）字段

条目 `{providerId, providerName, config}`；`config` 字段集合**固定**，字段顺序 `group → access → api → personalModelIds → modelOrder`，不可添加任何额外字段（无 enabled/source/kind/models/visibility/logo）：

| 字段 | 说明 |
|------|------|
| `group` | 固定 `"standard-personal"`（个人渠道唯一可用值） |
| `access` | `{type: "api-key", apiKey}`；**apiKey 只支持明文实值**，不支持 `{env:VAR}`、`!echo` 等任何环境变量形式（`resolveApiKey` 为恒等透传，占位符会原样发送导致鉴权失败） |
| `api` | `{type, baseUrl}`；`type` 枚举：`anthropic-messages` / `openai-chat-completions` / `openai-responses`；`baseUrl` 为真实 URL |
| `personalModelIds` | 该渠道的模型 id 数组 |
| `modelOrder` | 模型展示顺序，内容与 `personalModelIds` 相同、顺序一致 |

**providerId 命名**：内置渠道为 `builtin:xxx`；自定义渠道为 **baseURL 域名主体**（去掉子域名与顶级后缀；多段顶级后缀如 `com.cn` 取 3 段中的主体，如 `developer.amd.com.cn` → `amd`）。同主体不同 TLD 时确定性带顶级后缀消歧（`api.agnes-ai.cn`/`api.agnes-ai.com` → `agnes-ai-cn`/`agnes-ai-com`，`.` → `-`），**禁止** `-2`/`-3` 序号后缀（顺序依赖，重跑可能互换导致重复创建）；同一文件内不可重复。

**api.type 映射**（上游 OpenAI/Anthropic 协议 → zcode）：`openai-completions` → `openai-chat-completions`；`anthropic` → `anthropic-messages`。

## 模型条目字段

`providerModelRules[]` 条目 `{modelId, config, providerId}`，`config` **只写 `{enabled: true}`**——不写 properties/optionSpecs/displayName 等（写入多余字段会导致 schema 校验失败）。模型能力字段由渠道 UI 手动配置，不由本技能写入。

## 新增渠道步骤

1. `providerRules` 追加渠道条目（字段集合固定）；
2. `providerOrder` 追加新 `providerId`；
3. 每个模型追加一条 `providerModelRules` 条目；
4. `personalModelIds` 与 `modelOrder` 写入相同内容（模型 id 顺序一致）。

## 更新已有渠道

- 按 `providerName` 匹配渠道（先规范化：小写并去除非字母数字，再比较；不一致时用显式别名），或按 `baseUrl` 去尾斜杠精确匹配；
- 合并模型：向目标渠道 `personalModelIds`/`modelOrder` **两处都**追加新模型 id，并向 `providerModelRules` 追加对应条目；已有条目一律不动；
- 同一 `providerId+modelId` 不能同时出现在 `providerModelRules`（智能）与 `manualProviderModelRules`（手动）中；
- 更新密钥：解析 `<PREFIX>_API_KEY` 环境变量，写入明文 `access.apiKey`；
- 与本次同步无关的渠道/模型保持不变。

## 写入后校验

重新读取 JSON 解析，并核对：

- 渠道与模型条目的字段集合与文件中现有条目**完全一致**（多余的 `enabled`/`properties` 等字段即格式错误）；
- 渠道 `providerId` 无重复、`providerOrder` 含所有渠道 id；
- `personalModelIds` 与 `modelOrder` 内容一致；
- `api.type` 为合法枚举值、`baseUrl` 为合法 URL；
- 密钥为明文实值，且输出中不出现明文。

验证失败时保留备份、报告失败原因，不得宣称同步成功。

## 注意

- `access.apiKey` 明文只出现在配置文件的必要字段中，报告只说明"密钥已配置"；
- `api.type` 为 `anthropic-messages` 的渠道通常不支持 `GET {baseUrl}/models`，模型列表需由用户提供或从渠道 `personalModelIds` 读取；
- 备份文件含明文密钥，权限设为 `0600`，切勿提交到版本库。
