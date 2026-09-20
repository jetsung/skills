# qoder 配置参考（`~/.qoder/settings.json` 国外版 / `~/.qoder-cn/settings.json` 国内版）

「Qoder」国外版与国内版是**同一个软件**，仅版本目录不同：两份 `settings.json` 结构完全相同，`providers` 段即其 BYOK 模型存储（桌面版与 CLI 共用）。**同步目标检测：哪个目录存在就同步哪个；两个都存在则两个都同步，不再区分 qoder/qoder-cn/qodercli/qoderclicn**。

`~/.qoder/settings.json` 中的 `model`/`modelConfigs` 顶层键是 CLI 文档记载的配置项，与 `providers` 段并存互不冲突。

## 读取渠道配置

结构为 `providers.{渠道key}`，渠道 key 为 `qoder-custom-{UUID}`。字段为 `displayName`、`baseUrl`（渠道顶层、**小写 l**）、`apiKey`（**明文 key**）、`type`/`protocol`/`authType`、`model`（当前选中模型）、`models`（**数组**，元素含 `model`/`displayName`/`contextWindow`/`maxOutputTokens`/`capabilities`）：

```bash
# 示例：qoder（国外版目录；国内版把 .qoder 换成 .qoder-cn 即可）
python3 -c "
import json
c = json.load(open('$HOME/.qoder/settings.json'))
for k, p in c.get('providers', {}).items():
    print('KEY:', k)
    print('BASE_URL:', p['baseUrl'])
    print('TYPE:', p['type'])
    print('MODELS:', [m['model'] for m in p.get('models', [])])
"
```

> 注意：qoder 的 `apiKey` 为明文且位于渠道顶层（非 zcode 的 `access` 内）；`models` 是数组、id 字段名为 `model`（非 pi/dsh 的 `id`、非 zcode 的 `personalModelIds`），`baseUrl` 顶层小写 l（非 dsh 的 `baseURL` 全大写）。

## 写入格式

`providers.{渠道key}.models` 是**数组**，元素为 `{model, displayName, contextWindow, maxOutputTokens, capabilities}`：

```json
"providers": {
  "qoder-custom-f8e2d7da-22ba-4695-84b8-269b9703bab5": {
    "baseUrl": "https://newapi.idev.top/v1",
    "apiKey": "sk-xxx",
    "type": "openai-compatible",
    "protocol": "openai",
    "authType": "bearer",
    "model": "sense/deepseek-v4-flash",
    "models": [
      {
        "model": "sense/deepseek-v4-flash",
        "displayName": "sense/deepseek-v4-flash",
        "contextWindow": 200000,
        "maxOutputTokens": 8192,
        "capabilities": {
          "vision": false,
          "thinking": {
            "modes": [],
            "supportsEffort": false,
            "supportedEffortLevels": []
          }
        }
      }
    ],
    "displayName": "Qoder Custom F8e2d7da 22ba 4695 84b8 269b9703bab5"
  }
}
```

> qoder 的 `apiKey` 是**明文 key**（不是 `!echo` 环境变量形式），读取时直接取值，注意勿将密钥写入日志/输出。写入时**只更新 `models` 数组**，保留原 provider 的其它字段（displayName/baseUrl/apiKey/type/protocol/authType/model）不变；新增元素建议带 `model`（id 字段名）、`displayName`、`contextWindow`/`maxOutputTokens` 与 `capabilities` 结构，与文件原有格式一致（schema 见下）。

## provider 条目 schema 基准（同步写入的约束模板）

以真实条目 `providers["qoder-custom-6ef44237-5aac-40ae-8c6f-ca6f57164429"]` 为 schema 基准（可用 `jq -r '.providers["qoder-custom-6ef44237-5aac-40ae-8c6f-ca6f57164429"]' ~/.qoder-cn/settings.json` 提取对照）。同步/新建 provider 条目必须符合此结构，**不增删字段**：

```json
{
  "baseUrl": "https://hello.com/v1",
  "apiKey": "<明文 key>",
  "type": "openai-compatible",
  "protocol": "openai",
  "authType": "bearer",
  "displayName": "<渠道显示名>",
  "model": "<当前选中模型 id>",
  "models": [
    {
      "model": "<模型 id>",
      "displayName": "<{渠道显示名} - {模型名}>",
      "contextWindow": 1000000,
      "maxOutputTokens": 32000,
      "capabilities": {
        "vision": true,
        "thinking": {
          "modes": ["enabled"],
          "supportsEffort": true,
          "supportedEffortLevels": ["low", "medium", "high", "xhigh"]
        }
      }
    }
  ]
}
```

字段约束：
- **渠道级字段集合固定**：`baseUrl`/`apiKey`/`type`/`protocol`/`authType`/`displayName`/`model`/`models`，不添加额外字段；`type` 固定 `openai-compatible`、`protocol` 固定 `openai`、`authType` 固定 `bearer`
- **models 元素字段集合固定**：`model`（id）/`displayName`/`contextWindow`/`maxOutputTokens`/`capabilities`；id 字段名为 `model`（非 pi/dsh 的 `id`）
- **capabilities.thinking**：`modes` 为字符串数组（如 `["enabled"]`，无思考能力为 `[]`）、`supportsEffort` 布尔、`supportedEffortLevels` 档位数组（无思考能力为 `[]`）；`vision` 布尔
- `contextWindow`/`maxOutputTokens` 为正整数；同渠道内新增模型时优先参考该渠道现有元素的取值风格

## 渠道独立（重要）

每个 pi 渠道对应**独立的 provider**、**独立的密钥**、**独立的模型列表**：

- **匹配顺序**：baseUrl 去尾斜杠强绑定（唯一）→ ALIAS 显式映射 → 规范化 displayName（仅未占用、且未被其他渠道 baseUrl 强绑定的 provider）
- **自动创建**：无匹配的渠道自动新建 provider（key=`qoder-custom-{uuid4}`，结构与现有条目一致，含 baseUrl/apiKey/type/protocol/authType/model/models/displayName）
- **模型归属**：模型去供应商前缀后的短 id 属于哪个渠道就归哪个渠道；同步后 provider 只保留归属渠道的目标模型 + 用户手动添加的不属于任何渠道的模型，其它渠道的模型迁出（由各自渠道的 provider 接管）
- **独立密钥**：每个 provider 只写自己归属渠道的 apiKey（env 解析），互不覆盖；newapi 等中转渠道的模型（如 `sense/deepseek-latest-flash`）即使 id 前缀与其它渠道同名（`sense/deepseek-v4-flash`）也是独立模型，归中转渠道（newapi），密钥用中转渠道自己的
- **无目标模型渠道跳过**：模型为空或全非目标族的渠道不创建 provider、不写密钥（如 openrouter/opencode/kilo/v2ex/agnes）
- **displayName**：baseUrl 匹配/新建时更新为渠道显示名（纠正错误归属，如误设为 Sense 的 newapi provider 纠正为 NewAPI）；弱匹配（ALIAS/displayName）时已有值保留、空值补充

## CLI 模型配置（`model` / `modelConfigs` 顶层配置项）

配置文件分层（用户级/项目级/本地级，合并生效）：
- **用户级（同步目标）**：`~/.qoder/settings.json`（国外版）与 `~/.qoder-cn/settings.json`（国内版）；**禁止写项目级** `<项目>/.qoder/settings.json` 与本地级 `settings.local.json`
- JSON Schema 位于项目 `schemas/settings.schema.json`，可用于编辑器补全

| 配置项 | 类型 | 默认值 | 需重启 | 说明 |
|--------|------|--------|--------|------|
| `model.name` | string | 无 | 否 | 对话模型 |
| `model.reasoningEffort` | enum | 无 | 否 | 推理努力：`disabled`/`off`/`none`/`low`/`medium`/`high`/`xhigh`/`max` |
| `model.contextWindow` | number | 无 | 否 | 显式上下文窗口（token） |
| `model.summarizeToolOutput` | object | 无 | 否 | 按工具设置输出摘要 token 预算 |
| `modelConfigs.aliases` | object | 内置 | — | 模型配置别名预设 |
| `modelConfigs.customAliases` | object | `{}` | — | 自定义别名，合并覆盖内置 |
| `modelConfigs.overrides` | array | `[]` | — | 按匹配条件（主键为模型或别名）应用配置覆盖，最具体的匹配生效 |
| `modelConfigs.customOverrides` | array | `[]` | — | 自定义覆盖，与内置 overrides 合并追加 |

相关环境变量：`QODERCN_MODEL`（指定模型）、`QODERCN_SUBAGENT_MODEL`（子 Agent 模型）、`QODERCN_CONFIG_DIR`（配置目录，默认 `~/.qoder-cn`）。

**BYOK 自定义模型**（`providers.{渠道key}` 段即其存储形态，桌面版与 CLI 共用）：官方推荐经 `/model` → **Custom** 页签 → `Add custom model...` 向导添加（选 Provider → 模型类型 → 具体模型 → 填 API Key，验证通过自动保存）；同步写入时必须严格沿用文件中已有 provider 条目的完整结构（baseUrl/apiKey/type/protocol/authType/model/models/displayName），只合并 models 数组。删除模型在 Custom 页签按 `d`。

## qoder 专属同步规则

- 配置顶层同时含 `model`/`modelConfigs` 键与 `providers` 段（BYOK 模型存储，桌面版与 CLI 共用），渠道 key 为 `qoder-custom-{UUID}`（自动创建时生成 uuid4）；渠道字段：`displayName`/`baseUrl`（顶层、**小写 l**）/`apiKey`（**明文实值**，非占位符）/`type`/`protocol`/`authType`/`model`（当前选中模型）/`models`
- 顶层 `baseUrl`/`type`/`protocol`/`authType` 同步时**不动**；`model`（当前选中）用 pi 原样 id（允许去误加前缀规范化 + **版本族升级**，见下条）；`displayName` 在 baseUrl 匹配/新建时更新为渠道显示名，弱匹配时已有值保留（空值补充）
- **模型 id 保持 pi 原样**：不得擅自添加任何前缀（sense 渠道的 `deepseek-v4-flash` 就是 `deepseek-v4-flash`，不写 `sense/deepseek-v4-flash`；newapi 渠道的 `amd/deepseek-latest-flash` 本身带前缀则原样保留）；当前选中模型 `model` 字段同样用 pi 原样 id
- `apiKey`：**写死实值**（qoder 不支持 env 引用），每 provider 只写归属渠道的 env 值
- **展开**：每供应商的模型全部补入 models 数组；**模型筛选**：openrouter/opencode 渠道只补**免费模型**（id 含 `:free`/`-free`/`/free`），其它渠道**全量同步**；**模型 displayName 统一为 `{渠道显示名} - {模型名}` 格式**（如 `NewAPI - Sense DeepSeek Latest Flash`、`Sense - DeepSeek V4 Flash`；模型名已以渠道名开头则去重，如 amd 的 `AMD DeepSeek V4 Flash` → `AMD - DeepSeek V4 Flash`）
- **默认模型版本族规则（`model` 字段）**：同族（同一产品的不同版本号）模型存在更高版本时，`model` 自动取**同族最高版本**——如渠道 models 含 `agnes-2.0-flash`/`agnes-2.5-flash`/`agnes-3.0-flash` 而 `model` 为 `agnes-2.5-flash` 时，应升级为 `agnes-3.0-flash`。族键提取：模型 id 取**最后一个 `/` 后的段**（无 `/` 取全段）小写后提取**开头连续字母**（`^[a-z]+`，提取不到用整段，如 `agnes-2.5-flash` → `agnes`、`qwen3.8-27b` → `qwen`）；版本号 = 该段**首个数字串**（`2.5` → `(2,5)`，无数字 → 空元组视为最低）。同版本或均无版本号一律不动（幂等）；`model` 为空时取首个模型同族的最高版本

## 全量同步脚本

```bash
python3 scripts/sync-pi-to-qoder.py
```

目标配置：`~/.qoder/settings.json`（国外版）与 `~/.qoder-cn/settings.json`（国内版）（providers 段，按目录存在情况同步）；models 格式为数组（元素 id 字段名为 `model`，含 displayName/contextWindow/maxOutputTokens/capabilities）；apiKey **写死实值**（明文 apiKey，渠道顶层）。幂等可重复执行，自动备份+断言校验。
