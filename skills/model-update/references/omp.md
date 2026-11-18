# omp (Oh My Pi) 配置参考（`~/.omp/agent/models.yml`）

omp 的模型配置文件位于 `~/.omp/agent/models.yml`（`.yaml` 为次选；仅存在旧 `models.json` 时自动迁移为 `models.yml`），结构为 `providers.{渠道}.models` YAML 列表。根对象**只接受 `providers`**。完整文档见 [omp.sh/docs/custom-models](https://omp.sh/docs/custom-models)（页面为 JS 渲染，普通抓取只返回空壳，需从页面 JS 打包资源中提取文本）。多平台同步的完整说明见 `model-channel-sync` 技能的 `references/omp.md`。

本地推理服务免配置：omp 自动发现 Ollama（`http://127.0.0.1:11434`）、llama.cpp（`http://127.0.0.1:8080`）、LM Studio（`http://127.0.0.1:1234/v1`）。

**写入范围**：只写用户级 `~/.omp/agent/models.yml`，禁止修改项目级配置。

## 读取与写入格式

`providers.{渠道}.models` 是 **YAML 列表**（不是 pi 的 JSON 数组，也不是 opencode 的对象 map）：

```yaml
- id: stealth/ox-alpha
  name: Stealth OX Alpha (Free)
```

## 渠道（provider）字段

| 字段 | 说明 |
|------|------|
| `baseUrl` | 端点根 URL；`models` 非空时必填 |
| `api` | 声明/发现模型的默认 API（也可每个模型单独设） |
| `apiKey` | 环境变量**名**、`!command` 或字面量（解析规则见下）；声明模型必填，除非 `auth` 为 `none`/`oauth` |
| `auth` | `apiKey`（默认）/ `none` / `oauth`（仅限 omp 或扩展已支持的 OAuth，不能自定义新 OAuth 流程） |
| `headers` | 字符串请求头，值支持环境变量与 `!command` 解析 |
| `authHeader` | 为 `true` 时从 `apiKey` 注入 `Authorization: Bearer` 头（仅网关需要时设） |
| `models` | 该渠道拥有的完整模型定义（YAML 列表） |
| `discovery` | 动态目录：`type` + 可选 `timeoutMs`（正整数毫秒） |
| `modelOverrides` | 模型 id → 稀疏元数据补丁的 map（修补内置/发现模型） |
| `compat` | 高级请求/响应兼容覆盖（一般省略，让 omp 自动检测） |
| `disableStrictTools` | 对拒绝 strict tool-schema 的端点（常见于 Anthropic 兼容代理）禁用严格工具标记 |
| `remoteCompaction` | provider 级远程压缩配置（模型级值合并其上） |
| `guardrailIdentifier` / `guardrailVersion` / `guardrailTrace` | Amazon Bedrock guardrail 配置 |
| `transport` | 仅 `pi-native`，经 `omp auth-gateway` 路由（baseUrl=网关，apiKey=其 bearer） |

> 无 `models` 的 provider 条目是**修改内置 provider**（如给 `openai` 换 `baseUrl`/`apiKey`/`headers`），不替换其目录；此类条目必须至少设置一个有效覆盖（`baseUrl`/`headers`/`apiKey`/`auth: none`/`compat`/`disableStrictTools`/`modelOverrides`/`discovery` 等）。

### `api` 合法值

`openai-completions`（Chat Completions）、`openai-responses`（Responses API）、`openai-codex-responses`（Codex 风味）、`azure-openai-responses`、`anthropic-messages`、`bedrock-converse-stream`、`google-generative-ai`、`google-gemini-cli`、`google-vertex`。其它 wire 协议需扩展，不能靠加字符串。

OpenAI 兼容渠道用 `openai-completions`；上游为 Responses API 用 `openai-responses`；Anthropic Messages 端点用 `anthropic-messages`。

### `apiKey` 解析规则（与 pi 不同，务必转换）

1. 值以 `!` 开头 → 执行 shell 命令，取 stdout（trim 后）作为密钥
2. 否则查找**同名环境变量**（直接写变量名，**不带 `$`**，如 `apiKey: SENSE_API_KEY`）
3. 环境变量不存在 → 用配置文本作为**字面量**密钥

`headers` 值用同样规则。**不要把 pi 的 `!echo -n "$SENSE_API_KEY"` 或 `"$SENSE_API_KEY"` 原样抄进 omp**——按本技能约定应写环境变量名裸形式 `SENSE_API_KEY`。

## 模型（models 元素）字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 非空的上游模型 id |
| `name` | 否 | 选择器标签，默认 `id` |
| `api` / `baseUrl` | 否 | 覆盖 provider 级对应值（仅此模型） |
| `reasoning` | 否 | 标记支持推理；`thinking` 控制面生效的前提 |
| `thinking` | 否 | 显式 effort 控制（见下）；省略则由模型身份与兼容性自动决定 |
| `input` | 否 | `["text"]`（默认）或 `["text", "image"]` |
| `imageInputDecoder` | 否 | 图像解码器（如 `stb`） |
| `tokenizer` | 否 | 分词器标识（`claude-v3`/`claude-v47`/`claude-v5`/`claude-v5-sonnet`/`qwen3`/`deepseek-v3`/`kimi-k2`/`glm5`） |
| `supportsTools` | 否 | 端点是否支持工具调用 |
| `cost` | 否 | `{input, output, cacheRead, cacheWrite, premiumMultiplier}`（`premiumMultiplier` 作用于报告成本） |
| `contextWindow` / `maxTokens` | 否 | 正整数上下文/输出上限 |
| `omitMaxOutputTokens` | 否 | 为 `true` 时不发送 max-output-tokens 请求字段 |
| `headers` / `compat` | 否 | 模型级请求头（同名替换 provider 级）/ 模型级兼容覆盖 |
| `contextPromotionTarget` | 否 | 上下文超限时提升到 `provider/model-id` |
| `compactionModel` / `remoteCompaction` | 否 | 压缩偏好模型 / 每模型远程压缩设置 |
| `modelOverrides` | 否 | （嵌套）对该模型的稀疏补丁 |

> 新声明模型的默认值：name=id、text-only、无 reasoning、context 128000、maxTokens 16384、cost 全零。上游没有可靠数据的可选字段一律省略，不填默认值。

### `thinking` 结构

`reasoning: true` 时可设 `thinking: { mode, efforts, defaultLevel, effortMap, supportsDisplay, levels, minLevel, maxLevel }`：
- `mode`：`effort` / `budget` / `google-level` / `anthropic-adaptive` / `anthropic-budget-effort`
- `efforts`：支持的档位（`minimal`/`low`/`medium`/`high`/`xhigh`/`max`）
- `defaultLevel`：默认档位；`effortMap`：档位名 → 供应商专有字符串映射

### `discovery`（免维护 models 列表）

`discovery: { type: ..., timeoutMs: ... }`，type 取值：`ollama`、`llama.cpp`、`lm-studio`、`openai-models-list`（通用 `GET /v1/models`）、`litellm`（富元数据路由，回退 `/v1/models`）、`proxy`（OpenAI/Anthropic 混合代理，按 `supported_endpoint_types` 推导模型 API）。除 `proxy` 外都要求 provider 级 `api`。验证/刷新：`omp models <provider>`、`omp models refresh <provider>`。本技能按上游 `/models` 显式写 `models` 列表，不使用 `discovery`。

## 字段映射（上游 `/models` → omp）

| 上游/输入 | omp 字段 | 说明 |
|-----------|----------|------|
| `<PREFIX>_BASE_URL` 实值 | `providers.{渠道}.baseUrl` | **明文 URL**；不支持环境变量引用，`{env:...}` 是 opencode 语法，omp 不认 |
| `<PREFIX>_API_KEY` | `providers.{渠道}.apiKey` | 写**环境变量名裸形式**（如 `SENSE_API_KEY`，不带 `$`、不带 `!echo`），落盘不含明文 |
| 渠道标识 `channel` | `providers` 的键名 | omp 无独立渠道显示名字段，显示名只体现在 `models[].name` |
| 接口类型 | `providers.{渠道}.api` | OpenAI Chat Completions 为 `openai-completions`（取值集合见上） |
| `id` | `models[].id` | 保持上游原样，不擅自加/去前缀 |
| `name` / `display_name` | `models[].name` | 缺失时省略（omp 默认 name=id） |
| `context_length` | `models[].contextWindow` | 上游无数据则省略 |
| `max_tokens` | `models[].maxTokens` | Sense 渠道不写（见「渠道特定规则」） |
| 输入模态含图像 | `models[].input: [text, image]` | 仅上游明确提供时写入 |
| 推理能力 | `models[].reasoning: true` | Sense 渠道不写 |
| 价格 | `models[].cost` | 仅上游有可靠数据时写入，不做单位换算 |
| `output_modalities` 含 `image`/`video`/`audio` 或 chat 实测 404 | — | 生图/非文本模型**不写入**（omp 条目一律当聊天模型） |
| `output_modalities` 含 `decision` | — | 决策模型**不写入** omp |

## 新增 Sense 渠道示例

```yaml
providers:
  sense:
    baseUrl: https://token.sensenova.cn/v1
    api: openai-completions
    apiKey: SENSE_API_KEY
    models:
      - id: sensenova-6.8-flash-lite
        name: Sense Sensenova 6.8 Flash Lite
        contextWindow: 131072
```

`baseUrl` 取 `<PREFIX>_BASE_URL` 实值；`apiKey` 写环境变量名裸形式。免鉴权的本地 OpenAI 兼容服务可省略 `apiKey` 并设 `auth: none`：

```yaml
providers:
  local-openai:
    baseUrl: http://127.0.0.1:8000/v1
    api: openai-completions
    auth: none
    models:
      - id: Qwen/Qwen2.5-Coder-32B-Instruct
```

## 更新已有渠道

- `providers.{渠道}.models` 按 `id` upsert：同 id 替换条目、新 id 追加，不产生重复；自定义条目与现有模型同 provider 同 `id` 时替换该模型的传输配置。
- 保留同一文件内其他 provider 与其他模型，不自动删除本次未出现的手工模型。
- 渠道级字段（`baseUrl`、`api`、`apiKey`、`auth`、`headers` 等）**已有值不动**，仅缺失或为空时补入。
- `apiKey` 保留 omp 现有引用形式——同一渠道在 omp 里的环境变量名可能与本技能前缀不同，**不可覆盖**（`model-channel-sync` 侧的实测：omp 的 kilo 渠道用 `NVIDIA_API_KEY` 而非 `KILO_API_KEY`）。

## 渠道特定规则

- **Sense 渠道参数精简**：`baseUrl` 主机为 `token.sensenova.cn` / `token.sensenova.ai` 时，模型条目**不携带 `reasoning` 与 `maxTokens`**，已有条目中的这两个参数在同步/清理时一并移除；`contextWindow` 等其它参数照常。
- **生图模型不写入**：走 `/images/generations` 的模型在 omp 无可用路径。
- **决策模型（classifier）不写入**：omp 无 classifier 注册能力，只经 pi provider extension 使用。

## 写入后校验

```bash
python3 -c "import yaml,sys;yaml.safe_load(open(sys.argv[1]))" ~/.omp/agent/models.yml
```

再确认：根对象只有 `providers`、渠道存在、`baseUrl` 为明文 URL、`api` 合法、`apiKey` 为裸环境变量名（不含 `$`、`!` 或明文密钥）、`models` 为列表且 `id` 唯一、条目数量与本批转换结果一致。格式校验失败时 omp 会提示 `models.yml validation failed` 并给出出错字段；单个模型可用性能实测：

```bash
omp -p --model <provider>/<model-id> "Reply with only OK"
```

## 注意

- 每次真实写入前创建带时间戳备份（如 `models.yml.bak-YYYYMMDDHHMMSS`），验证失败时用备份恢复。
- `apiKey` 写环境变量名裸形式，配置与备份中**不得出现明文密钥**；若该渠道在 omp 中原本就是字面量明文，文件与备份权限设 `0600`，报告只说明"密钥已配置"。
- 与 `model-channel-sync` 的差异：那里的输入是 pi 配置（`!echo -n "$VAR"`），本技能的输入是上游 `/models` 缓存；两者的 omp 落盘格式规则一致。
