# qoder 配置参考（`~/.qoder/settings.json` 国外版 / `~/.qoder-cn/settings.json` 国内版）

「Qoder」国外版与国内版是**同一个软件**，仅版本目录不同：两份 `settings.json` 结构完全相同，`providers` 段即其 BYOK 模型存储（**桌面版与 CLI 共用**）。**写入目标检测：哪个目录存在就写哪个；两个都存在则两个都写**，不再区分 qoder/qoder-cn/qodercli/qoderclicn。

`~/.qoder/settings.json` 中的 `model`/`modelConfigs` 顶层键是 CLI 文档记载的配置项，与 `providers` 段并存互不冲突。

**写入范围**：只写用户级 `settings.json`，**禁止写项目级** `<项目>/.qoder/settings.json` **与本地级** `settings.local.json`。

## 读取与写入格式

结构为 `providers.{渠道key}`，渠道 key 为 `qoder-custom-{UUID}`（自动创建时生成 uuid4）。`models` 是**数组**，元素 id 字段名为 **`model`**（不是 pi/dsh 的 `id`，也不是 zcode 的 `personalModelIds`）：

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

> 三处易错点：`apiKey` 为**明文**且位于**渠道顶层**（不在 `access` 之类子对象内）；`models` 是数组、id 字段名 `model`；`baseUrl` 在顶层且**小写 l**（不是 dsh 的 `baseURL`）。

## 渠道（provider）字段

字段集合**固定、不增删**：

| 字段 | 说明 |
|------|------|
| `baseUrl` | 端点地址（顶层、小写 l）；同步时**不动** |
| `apiKey` | **明文实值**（qoder 不支持环境变量引用）；同步时只写归属渠道的密钥 |
| `type` | 固定 `openai-compatible` |
| `protocol` | 固定 `openai` |
| `authType` | 固定 `bearer` |
| `displayName` | 渠道显示名 |
| `model` | 当前选中模型 id |
| `models` | 模型数组 |

## 模型（models 元素）字段

字段集合**固定、不增删**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `model` | string | 模型 id，原样传给 API |
| `displayName` | string | 显示名，统一 `{渠道显示名} - {模型名}` |
| `contextWindow` | number | 正整数；同渠道内新增模型时优先参考该渠道现有元素取值风格 |
| `maxOutputTokens` | number | 正整数 |
| `capabilities` | object | `{vision, thinking}` |
| `capabilities.vision` | bool | 是否支持图像输入 |
| `capabilities.thinking.modes` | string[] | 思考模式（如 `["enabled"]`，无思考能力为 `[]`） |
| `capabilities.thinking.supportsEffort` | bool | 是否支持 effort 档位 |
| `capabilities.thinking.supportedEffortLevels` | string[] | 档位数组（如 `["low","medium","high","xhigh"]`，无为 `[]`） |

## 字段映射（上游 `/models` → qoder）

| 上游/输入 | qoder 字段 | 说明 |
|-----------|-----------|------|
| `<PREFIX>_BASE_URL` 实值 | `providers.{渠道key}.baseUrl` | 真实地址；渠道匹配用去尾斜杠比较 |
| `<PREFIX>_API_KEY` **实值** | `providers.{渠道key}.apiKey` | **写死明文**，qoder 无 env 引用能力；每个 provider 只写自己归属渠道的密钥，互不覆盖 |
| 渠道标识 / 显示名 | `qoder-custom-{uuid4}` + `displayName` | key 自动创建时生成；`displayName` 在 baseUrl 匹配/新建时更新为渠道显示名 |
| 接口类型 | `type` / `protocol` / `authType` | OpenAI Chat Completions 兼容即 `openai-compatible` / `openai` / `bearer` |
| `id` | `models[].model` | 上游原样，**不擅自加或去前缀**（sense 的 `deepseek-v4-flash` 不写成 `sense/deepseek-v4-flash`；渠道自带前缀如 `amd/deepseek-latest-flash` 原样保留） |
| `name` / `display_name` | `models[].displayName` | 统一 `{渠道显示名} - {模型名}`；模型名已以渠道名开头则去重 |
| `context_length` | `models[].contextWindow` | 正整数 |
| `max_tokens` | `models[].maxOutputTokens` | 正整数 |
| 输入模态含图像 | `capabilities.vision: true` | 否则 `false` |
| 推理能力 | `capabilities.thinking` 三项 | 无思考能力时 `modes: []`、`supportsEffort: false`、`supportedEffortLevels: []` |
| `output_modalities` 含 `image`/`video`/`audio` 或 chat 实测 404 | — | 生图/非文本模型**不写入**（模型条目只有上述五个字段，无生图注册路径） |
| `output_modalities` 含 `decision` | — | 决策模型**不写入** qoder |

## 渠道独立（重要）

每个渠道对应**独立的 provider、独立的密钥、独立的模型列表**：

- **匹配顺序**：`baseUrl` 去尾斜杠强绑定（唯一）→ ALIAS 显式映射 → 规范化 `displayName`（仅未占用、且未被其他渠道 `baseUrl` 强绑定的 provider）
- **自动创建**：无匹配的渠道新建 provider（key = `qoder-custom-{uuid4}`，结构与现有条目一致，含全部 8 个渠道字段）
- **模型归属**：模型去供应商前缀后的短 id 属于哪个渠道就归哪个渠道；中转渠道（如 newapi）的模型即使 id 前缀与其它渠道同名也是独立模型，归中转渠道、用中转渠道自己的密钥
- **无目标模型渠道跳过**：模型为空或全非目标族的渠道不创建 provider、不写密钥
- **`displayName`**：baseUrl 匹配/新建时更新为渠道显示名（纠正错误归属）；弱匹配（ALIAS/displayName）时已有值保留、空值补充

## 新增渠道示例

```json
{
  "providers": {
    "qoder-custom-6ef44237-5aac-40ae-8c6f-ca6f57164429": {
      "baseUrl": "https://token.sensenova.cn/v1",
      "apiKey": "<SENSE_API_KEY 的明文实值>",
      "type": "openai-compatible",
      "protocol": "openai",
      "authType": "bearer",
      "displayName": "Sense",
      "model": "sensenova-6.8-flash-lite",
      "models": [
        {
          "model": "sensenova-6.8-flash-lite",
          "displayName": "Sense Sensenova 6.8 Flash Lite",
          "contextWindow": 131072,
          "maxOutputTokens": 8192,
          "capabilities": {
            "vision": false,
            "thinking": { "modes": [], "supportsEffort": false, "supportedEffortLevels": [] }
          }
        }
      ]
    }
  }
}
```

## 更新已有渠道

- **只合并 `models` 数组**：按 `model`（id）upsert，同 id 更新、新 id 追加；保留原 provider 的其它字段不变。
- 顶层 `baseUrl`/`type`/`protocol`/`authType` 同步时**不动**；`model`（当前选中）用上游原样 id。
- **默认模型版本族升级**：同族（同一产品的不同版本号）存在更高版本时，`model` 自动取**同族最高版本**（如 models 含 `agnes-2.0-flash`/`agnes-2.5-flash`/`agnes-3.0-flash` 而 `model` 为 `agnes-2.5-flash` → 升级为 `agnes-3.0-flash`）。族键提取：id 取**最后一个 `/` 后的段**（无 `/` 取全段）小写后提取**开头连续字母**（`^[a-z]+`，提取不到用整段，如 `agnes-2.5-flash` → `agnes`、`qwen3.8-27b` → `qwen`）；版本号 = 该段**首个数字串**（`2.5` → `(2,5)`，无数字 → 空元组视为最低）。同版本或均无版本号一律不动（幂等）；`model` 为空时取首个模型同族的最高版本。
- 保留与本次同步无关的 provider 与手工模型，不自动删除。

## CLI 模型配置（`model` / `modelConfigs` 顶层配置项）

配置分层（用户级/项目级/本地级，合并生效），JSON Schema 位于项目 `schemas/settings.schema.json`。与模型同步相关的条目：

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

**BYOK 自定义模型**（`providers.{渠道key}` 段即其存储形态）：官方推荐经 `/model` → **Custom** 页签 → `Add custom model...` 向导添加（选 Provider → 模型类型 → 具体模型 → 填 API Key，验证通过自动保存）；脚本写入时必须严格沿用文件中已有 provider 条目的完整结构，只合并 `models` 数组。删除模型在 Custom 页签按 `d`。

## 写入后校验

```bash
python3 -m json.tool ~/.qoder-cn/settings.json > /dev/null
python3 -m json.tool ~/.qoder/settings.json > /dev/null   # 目录存在时
```

再确认：渠道 `baseUrl` 与上游一致、`type`/`protocol`/`authType` 为固定三值、`models` 元素字段集合恰为 `{model, displayName, contextWindow, maxOutputTokens, capabilities}`、`model`（id）在渠道内唯一且与本批一致、`model`（当前选中）存在且已做版本族升级、两份目录（若都存在）内容一致。

## 注意

- **`apiKey` 为明文实值**：属敏感文件，**切勿提交到版本库或外发**；文件与时间戳备份权限设 `0600`；报告只说明密钥长度/变化状态，检查配置时过滤 `apiKey`/`api_key`，绝不输出明文。
- 每次真实写入前创建带时间戳备份，验证失败时用备份恢复。
- qoder 无 classifier（决策模型）与生图模型的注册路径：模型条目字段集合固定，两类模型一律不写入，报告中注明剔除原因。
