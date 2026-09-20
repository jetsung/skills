# omp (Oh My Pi) 配置参考（`~/.omp/agent/models.yml`）

omp 的模型配置文件位于 `~/.omp/agent/models.yml`（`.yaml` 为次选；仅存在旧 `models.json` 时自动迁移为 `models.yml`），结构为 `providers.{渠道}.models` YAML 列表。根对象**只接受 `providers`**。完整文档见 [omp.sh/docs/custom-models](https://omp.sh/docs/custom-models)。注意：omp 文档页面为 JS 渲染，普通抓取只返回空壳，需从页面 JS 打包资源中提取文本。

本地推理服务免配置：omp 自动发现 Ollama（`http://127.0.0.1:11434`）、llama.cpp（`http://127.0.0.1:8080`）、LM Studio（`http://127.0.0.1:1234/v1`）。

## 读取与写入格式

`providers.{渠道}.models` 是 **YAML 列表**：

```yaml
- id: stealth/ox-alpha
  name: Stealth OX Alpha (Free)
```

## omp Provider 字段

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

> 无 `models` 的 provider 条目必须至少设置一个有效覆盖（`baseUrl`/`headers`/`apiKey`/`auth: none`/`compat`/`disableStrictTools`/`modelOverrides`/`discovery` 等），否则无意义。

## omp 的 `api` 值

`openai-completions`（Chat Completions）、`openai-responses`（Responses API）、`openai-codex-responses`（Codex 风味）、`azure-openai-responses`、`anthropic-messages`、`bedrock-converse-stream`、`google-generative-ai`、`google-gemini-cli`、`google-vertex`。其它 wire 协议需扩展，不能靠加字符串。

## omp 的 `apiKey` 解析规则（与 pi 不同）

1. 值以 `!` 开头 → 执行 shell 命令，取 stdout（trim 后）作为密钥
2. 否则查找**同名环境变量**（直接写变量名，**不带 `$`**，如 `apiKey: MYCO_LLM_API_KEY`）
3. 环境变量不存在 → 用配置文本作为**字面量**密钥

`headers` 值用同样规则。这与 pi 的 `!echo -n "$VAR"` / `"$VAR"` 形式不同，同步时须按目标格式转换。

## omp Model 字段

| 字段 | 说明 |
|------|------|
| `id` | 必填，非空的上游模型 id |
| `name` | 选择器标签，默认 `id` |
| `api` / `baseUrl` | 覆盖 provider 级对应值（仅此模型） |
| `reasoning` | 标记支持推理；`thinking` 控制面生效的前提 |
| `thinking` | 显式 effort 控制（见下）；省略则由模型身份与兼容性自动决定 |
| `input` | `["text"]`（默认）或 `["text", "image"]` |
| `imageInputDecoder` | 图像解码器（如 `stb`） |
| `tokenizer` | 分词器标识（`claude-v3`/`claude-v47`/`claude-v5`/`claude-v5-sonnet`/`qwen3`/`deepseek-v3`/`kimi-k2`/`glm5`） |
| `supportsTools` | 端点是否支持工具调用 |
| `cost` | `{input, output, cacheRead, cacheWrite, premiumMultiplier}`（`premiumMultiplier` 作用于报告成本） |
| `contextWindow` / `maxTokens` | 正整数上下文/输出上限 |
| `omitMaxOutputTokens` | 为 `true` 时不发送 max-output-tokens 请求字段 |
| `headers` | 模型级请求头（同名替换 provider 级） |
| `compat` | 模型级兼容覆盖 |
| `contextPromotionTarget` | 上下文超限时提升到 `provider/model-id` |
| `compactionModel` / `remoteCompaction` | 压缩偏好模型 / 每模型远程压缩设置 |
| `modelOverrides` | （嵌套）对该模型的稀疏补丁 |

> 新声明模型的默认值：name=id、text-only、无 reasoning、context 128000、maxTokens 16384、cost 全零。

## omp 的 `thinking` 字段

`reasoning: true` 时可设 `thinking: { mode, efforts, defaultLevel, effortMap, supportsDisplay, levels, minLevel, maxLevel }`：
- `mode`：`effort` / `budget` / `google-level` / `anthropic-adaptive` / `anthropic-budget-effort`
- `efforts`：支持的档位（`minimal`/`low`/`medium`/`high`/`xhigh`/`max`）
- `defaultLevel`：默认档位；`effortMap`：档位名 → 供应商专有字符串映射

```yaml
- id: deepseek-v4-pro
  reasoning: true
  thinking:
    mode: effort
    efforts: [low, medium, high]
    defaultLevel: medium
```

## omp 的 `discovery`（免维护 models 列表）

`discovery: { type: ..., timeoutMs: ... }`，type 取值：`ollama`（Ollama 原生端点）、`llama.cpp`、`lm-studio`、`openai-models-list`（通用 `GET /v1/models`）、`litellm`（富元数据路由，回退 `/v1/models`）、`proxy`（OpenAI/Anthropic 混合代理，按 `supported_endpoint_types` 推导模型 API）。除 `proxy` 外都要求 provider 级 `api`。验证/刷新：`omp models <provider>`、`omp models refresh <provider>`。

## omp 的覆盖机制

- 不带 `models` 的 provider 条目是**修改内置 provider**（如给 `openai` 换 `baseUrl`/`apiKey`/`headers`），不替换其目录
- `modelOverrides` 逐模型补丁（`gpt-5.4: {contextWindow: 400000}`）
- 自定义 `models` 条目与现有模型同 provider 同 `id` 时，替换该模型的传输配置
- 验证失败提示 `models.yml validation failed` + 出错字段；实测：`omp -p --model <provider>/<model-id> "Reply with only OK"`

## omp 最小与完整示例

```yaml
# 最小（免鉴权 OpenAI 兼容服务）
providers:
  local-openai:
    baseUrl: http://127.0.0.1:8000/v1
    api: openai-completions
    auth: none
    models:
      - id: Qwen/Qwen2.5-Coder-32B-Instruct
```

```yaml
# 完整（远端服务 + 环境变量密钥）
providers:
  myco:
    baseUrl: https://llm.internal.example/v1
    apiKey: MYCO_LLM_API_KEY
    api: openai-responses
    models:
      - id: myco-large
        name: MyCo Large
        reasoning: true
        input: [text, image]
        contextWindow: 200000
        maxTokens: 32000
        cost:
          input: 3
          output: 15
          cacheRead: 0.3
          cacheWrite: 3.75
```

## 写入 omp 时的要点（汇总）

- 只写全局 `~/.omp/agent/models.yml`，禁止项目级
- `models` 是 YAML 列表，元素 `{id, name}` 起步，有数据时补 `reasoning`/`input`/`contextWindow`/`maxTokens`/`cost`
- `apiKey` 用 env 变量名裸形式（omp 的解析规则），同步保留 omp 现有引用（env 名可能不同，如 omp kilo 用 `NVIDIA_API_KEY`，不可覆盖）
- `baseURL`/`api` 等渠道字段：已有值不动，缺失/为空才从 pi 补入
- 写回后用 `python3 -c "import yaml;yaml.safe_load(open(...))"` 校验

## 全量同步脚本

```bash
python3 scripts/sync-pi-to-omp.py
```

目标配置：`~/.omp/agent/models.yml`；models 格式为列表 `{id, name}`；apiKey 保留 `!echo` 占位符（env 名可能不同，如 omp kilo 用 `NVIDIA_API_KEY` 而非 `KILO_API_KEY`，不可覆盖）。幂等可重复执行，自动备份+断言校验。
