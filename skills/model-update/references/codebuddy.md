# codebuddy 配置参考（`~/.codebuddy/models.json`）

codebuddy（腾讯云 CodeBuddy，CLI 与 IDE 共用同一文件）的模型配置位于用户级 `~/.codebuddy/models.json`，结构为**扁平 `models` 数组 + 可选 `availableModels` 白名单**，没有渠道（provider）层级——每个模型是一条自包含条目，`url` 与 `apiKey` 都写在模型条目上。

官方文档：IDE <https://www.codebuddy.cn/docs/ide/Features/models>（`models.json 配置指南`）；CLI <https://www.codebuddy.cn/docs/cli/models>。两份文档描述同一文件，差异见「CLI 与 IDE 文档的差异」。

**写入范围**：只写用户级 `~/.codebuddy/models.json`，**禁止修改项目级** `<workspace>/.codebuddy/models.json`（项目级优先级更高、且属于项目仓库文件）。

## 顶层结构

```json
{
  "models": [
    {
      "id": "deepseek-chat",
      "name": "DeepSeek Chat",
      "vendor": "DeepSeek",
      "url": "https://api.deepseek.com/v1/chat/completions",
      "apiKey": "sk-实际密钥值",
      "maxInputTokens": 32000,
      "maxOutputTokens": 4096,
      "supportsToolCall": true,
      "supportsImages": false,
      "supportsReasoning": false
    }
  ],
  "availableModels": ["deepseek-chat"]
}
```

## 模型条目（LanguageModel）字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✓ | 模型唯一标识符（原样发给 API）；**全数组唯一**，同 `id` 会被 SmartMerge 覆盖 |
| `name` | string | — | 显示名称（IDE 故障排查段落把它与 `vendor` 列为必填，写入时一律补齐） |
| `vendor` | string | — | 渠道/供应商显示名（真实字段名是 `vendor`，文档某段误写作 `provider`） |
| `url` | string | — | API 端点，**必须是完整路径**，一般以 `/chat/completions` 结尾；只写 `https://api.example.com/v1` 是错的 |
| `apiKey` | string | — | API 密钥（明文实值，见下） |
| `maxInputTokens` | number | — | 最大输入 token 数（≈ 上下文窗口） |
| `maxOutputTokens` | number | — | 最大输出 token 数 |
| `supportsToolCall` | boolean | — | 是否支持工具调用 |
| `supportsImages` | boolean | — | 是否支持图片输入 |
| `supportsReasoning` | boolean | — | 是否支持推理模式 |
| `temperature` | number | — | 采样温度 0–2（仅 CLI 文档记载，本技能不主动写入） |
| `relatedModels` | object | — | 场景关联模型 `lite`/`reasoning`（仅 CLI 文档记载，本技能不主动写入） |
| `useCustomProtocol` | boolean | — | 仅 CLI 侧使用；保持文件中现有值 |

**接口限制**：目前**仅支持 OpenAI Chat Completions 格式**的 API。Anthropic 原生 `messages`、Responses API 等非该格式的渠道不能配到 codebuddy。

`availableModels`（`Array<string>`）：控制下拉列表显示哪些模型 id；**未配置或为空数组 = 显示全部**，一旦配置则只显示列出的 id（可混合内置与自定义 id）。经 `models.json` 添加的模型自动带 `custom` 标签。

**配置优先级**（高→低）：项目级 `models.json` → 用户级 `models.json` → 内置默认。合并策略 SmartMerge：同 `id` 覆盖、不同 `id` 追加；`availableModels` 在所有合并完成后执行过滤，且项目级**完全覆盖**用户级、不合并。用内置 `id`（如 `gpt-4-turbo`）写条目即改写该内置模型的端点与密钥。

**热重载**：文件变更自动检测（1 秒防抖），保存即生效，无需重启。

## 字段映射（上游 `/models` → codebuddy）

| 上游字段 | codebuddy 字段 | 说明 |
|----------|----------------|------|
| `id` | `id` | 原样；与其它渠道重名时加渠道前缀（见「同模型多渠道」） |
| `name` / `display_name` | `name` | 缺失时用 `{vendor} - {id}` |
| 渠道显示名 | `vendor` | 如 `Sense`、`AMD` |
| `<CHANNEL>_BASE_URL` | `url` | 去尾斜杠；不以 `/chat/completions` 结尾则拼接该路径 |
| `<CHANNEL>_API_KEY` 实值 | `apiKey` | **写死明文实值** |
| `context_length` / `contextWindow` | `maxInputTokens` | |
| `max_tokens` / `maxTokens` | `maxOutputTokens` | |
| `input` / `architecture.input_modalities` 含 `image` | `supportsImages: true` | |
| `reasoning` 为 true | `supportsReasoning: true` | |
| — | `supportsToolCall: true` | 默认 true |

## 密钥规则（重要）

- codebuddy **只认明文实值**：IDE 文档明确 `apiKey` 为「实际密钥值，非环境变量名」，通篇不提供变量引用；CLI 文档虽提到 `${VAR_NAME}`，但变量不存在时保留原占位符并导致调用失败。故按本技能约定，取 `<CHANNEL>_API_KEY` 的**环境变量实值**写入 `apiKey`。
- 明文只出现在配置文件的 `apiKey` 字段中，报告中**不得输出密钥**（只说「密钥已配置」）。
- 文件与备份权限设为 `0600`，切勿提交到版本库。

## 新增渠道（一批模型）步骤

1. 逐模型构造条目（`id`/`name`/`vendor`/`url`/`apiKey` 必写，其余按上游实际提供的字段补）；
2. 向 `models` 数组**追加**新条目；已存在同 `id` 条目按 upsert 处理（只补缺失字段，不改用户已设置的值）；
3. 若文件里已存在**非空** `availableModels`，把新增 id 一并追加进去——否则新模型不会出现在下拉列表；`availableModels` 缺失或为空则无需创建（表示显示全部）；
4. 保存后核对 JSON 可解析、`id` 唯一。

## 更新已有渠道

- 渠道匹配靠 `url`（同一 `/chat/completions` 完整路径）或 `vendor`；因无渠道层级，「更新渠道」实际等于**按 id upsert 该端点下的模型条目**；
- 只增不删：上游下架、文件中残留的条目不会自动移除；与本批无关的条目（含手工条目、内置模型覆盖条目）保持原样；
- 现有条目的 `${VAR}` 形式 `apiKey` 可按需转换为明文（属用户配置变更，需用户同意后再做）。

## 同模型多渠道（id 冲突）

`id` 在扁平数组中必须唯一，而上游同一模型常出现在多个渠道（如 `glm-5.2` 同时在 sense 与 newapi）。处理：

- 按渠道优先级（专用渠道优先，聚合/免费网关靠后）只保留一条；或
- 给重名条目加渠道前缀作为 `id`（如 `agnes-com/glm-5.2`、`sense-ai/kimi-k3`），`vendor` 用对应渠道显示名以区分。

前缀写法要求上游接受 `<前缀>/<模型>` 形式的 id（聚合网关通常接受）；不确定时先实测再写入。

## CLI 与 IDE 文档的差异

| 项 | CLI 文档 | IDE 文档 | 取舍 |
|----|----------|----------|------|
| 独有字段 | `temperature`、`relatedModels`、`useCustomProtocol` | 未记载 | 只写两侧都认的字段；现有条目已带的保留不动 |
| `apiKey` | 支持 `${VAR_NAME}` 引用（变量缺失则原样发送导致失败） | 明确「实际密钥值，非环境变量名」 | 写死明文实值 |
| 接口类型 | 未单独强调 | 明确「仅支持 OpenAI 接口格式」，`url` 必须完整路径 | 非 OpenAI Chat Completions 渠道不配 |
| 必填字段 | 只有 `id` | 字段表只有 `id`，故障排查段落又写 `id`/`name`/`provider`（`provider` 非真实字段名） | 一律补齐 `id`+`name`+`vendor` |

## 写入后校验

```bash
python3 -m json.tool ~/.codebuddy/models.json > /dev/null
```

再确认：

- 文件可解析；`models` 为数组且 `id` 无重复；
- 本批新增条目的 `url` 均以 `/chat/completions` 结尾（或原为完整路径）、`apiKey` 为明文实值、`vendor`/`name` 非空；
- 若存在非空 `availableModels`，本批 id 均已列入；
- 条目数量 = 备份中的数量 + 本批新增数量（只增不删）；
- 输出与报告中不出现明文密钥。

验证失败时保留备份、报告原因，不得宣称同步成功；必要时用备份恢复。

## classifier / 非文本模型

codebuddy 只有聊天模型概念（`supportsImages` 表示能吃图片输入），**没有** pi 的 classifier（决策模型）类型，也不支持图片生成类模型：`output_modalities` 含 `decision` 的模型与纯图/视频/音频输出模型一律不写入 codebuddy。
