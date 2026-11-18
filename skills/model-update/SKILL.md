---
name: model-update
description: >-
  从上游渠道获取模型列表并新增/更新到目标 AI 平台配置：读取 <CHANNEL>_BASE_URL 与
  <CHANNEL>_API_KEY，请求 OpenAI 兼容 /models，缓存到 ~/.cache/models/<渠道>.jsonc，
  由 AI 依据目标平台格式生成字段映射，再按模型 id 幂等合并、备份并校验写入。
  当用户说「添加/更新 <渠道> 渠道到 <平台>」「把 XX 渠道的模型更新到 pi」「给 pi 加 XX 渠道」
  或要求从上游渠道同步模型到某平台时使用。
compatibility: Requires python3 and network access to the upstream channel's /models endpoint.
metadata:
  version: "1.7.0"
---

# 模型渠道新增与更新（上游 → 目标平台）

从上游渠道的 `/models` 接口抓取模型列表，按目标平台的配置格式新增或更新渠道及其全部模型。目标平台格式是转换权威，字段映射由执行本技能的 AI 依据语义生成，脚本只负责确定性的抓取、缓存与批量复制。

**目录结构**：
- `references/` — 各目标平台配置格式（写入前必读，按需渐进加载）；另含渠道 API 参数 schema（`references/<渠道名>.schema.json`，见「渠道文档与参数 schema」节）
- `scripts/fetch_models.py` — 读取环境变量、请求 `/models`、原子写入源缓存
- `scripts/test_models.py` — chat 实测模型可用性（429 可用/404 生图判定/多模态预筛剔除），输出可写入清单
- `scripts/apply_mapping.py` — 按 `目标字段=源字段` 映射批量转换模型条目

## 触发时机

- "添加/更新 <渠道> 渠道到 <平台>"
- "把 sense 渠道的模型更新到 pi"
- "给 pi 加上 sense 渠道"
- "从上游渠道同步模型到 omp/opencode/…"

## 输入解析

从请求中确定三要素，缺一不可：

| 要素 | 说明 |
|------|------|
| 渠道标识 `channel` | 用户给出的渠道名（如 `sense`、`sense-ai`）；决定环境变量前缀、缓存文件名和目标渠道 key |
| 目标平台 `platform` | 如 `pi`；必须能对应 `references/<platform>.md` |
| 渠道显示名 | 可选；未指定时使用 `channel` |

环境变量前缀：`channel` 转大写、非字母数字替换为 `_`，例如 `sense-ai` → `SENSE_AI`，对应 `SENSE_AI_BASE_URL`、`SENSE_AI_API_KEY`。

若目标平台没有参考文件，先依据其官方文档与用户级现有配置确认结构，补写 `references/<platform>.md` 后再继续；**目标平台格式永远是转换权威**，不得让上游字段名反向决定目标结构。

## 工作流程

`环境变量检查 → /models 抓取 → 源缓存 → 可用性实测 → 读取目标格式 → AI 映射 → 批量转换 → 渠道新增约束检查 → 备份与合并 → 写后验证`

### 1. 检查环境变量（任何写入前）

确认 `<PREFIX>_BASE_URL` 与 `<PREFIX>_API_KEY` 均存在且非空：

```bash
test -n "$SENSE_BASE_URL" && test -n "$SENSE_API_KEY" && echo "凭据已配置"
```

任一缺失或为空时**立即停止**，报告缺失的变量名，不修改目标配置。只检查存在性，**绝不回显变量值**。

### 2. 抓取上游模型并写入源缓存

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/fetch_models.py <channel>
```

- 成功：原始响应保存到 `~/.cache/models/<channel 小写>.jsonc`（保留上游全部字段），输出模型数量。
- **抓取请求优先用 curl，urllib 仅兜底**：`fetch_models.py` 的 `_request_models` 已改为 **curl 主请求（`_curl_get`）+ urllib 回退**——部分服务器（如 `apihub.agnes-ai.com`）对 Python urllib 的 TLS 握手**稳定挂起**（OpenSSL 3.5.9 与服务器不兼容），优先 curl 可避免此问题。修改抓取代码时保持此顺序：**先 curl 后 urllib**，勿颠倒；curl 不可用/异常或响应非 JSON 时回退 urllib。
- 失败（凭据缺失、网络错误、HTTP 错误、响应无模型数组）：脚本非零退出，**本次流程停止**，不写入目标配置。旧缓存保留仅供诊断，不得用于本次写入。
- 缓存不含 API Key。再次成功抓取时以本次结果整体替换旧缓存，不混用旧模型。

### 3. 可用性实测（任何写入前）

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_models.py <channel> [模型id ...]
```

不传模型 id 时按源缓存全量逐个 chat 实测（`max_tokens=8` 最小请求）；传 id 则只测指定模型。判定规则（与 `model-channel-sync` 一致）：

- HTTP 200 且 `choices` 的 content/reasoning 有值 → **可用**（推理模型 content 为 null 但 reasoning 有值也算可用）
- HTTP 429（`rate limit` / `inference exceeds tpm/rpm limit`）→ **可用**（临时限流，模型存在，不得剔除）
- HTTP 404 `model is not found` 但模型在 /models 缓存列表中 → **生图模型**（只走 `/images/generations`；404 即判定信号，无需二次探测），**不得写入只支持聊天模型的平台**（pi/omp/codebuddy/atomcode/qoder/opencode 把配置条目一律当聊天模型，生图无可用路径；已有遗留条目在同步/清理时移除）
- 403 含 region / token plan → **不可用**（地区/套餐限制）；其余 401/404（列表也无）/5xx/连接失败 → **不可用**
- 缓存条目 `output_modalities`/`output` 不含 text（图/视频/音频输出）或 id 含 `ocr` 的模型**预筛剔除**，不发起实测（省配额）

后续映射与写入**只处理小结中标为可用的模型**；生图模型与不可用模型在报告中列出剔除原因。**全部模型不可用（退出码 1）时停止写入**，报告实测明细。

### 4. 读取目标平台格式

读取 `references/<platform>.md` 和用户级现有配置，确认：渠道层级、模型条目结构、必填/可选字段、接口类型名称、密钥引用能力。目标现有配置只用于识别真实字段与平台能力，不用于反向推翻目标结构。

### 5. 生成、校验或复用字段映射

映射文件：`~/.cache/models/<platform>_from_<channel>.env`（平台与渠道均小写），每行一条 `目标平台字段=源渠道字段`，允许 `#` 注释与空行；**不得写入模型值或密钥**。

流程：

1. 读取源缓存中的**首个模型**（必要时兼看其他模型样本）与目标平台的模型结构。
2. 逐一判断字段语义，只映射可靠对应；`id=id`、`name=name` 也要明确写出。
3. **禁止脚本语义猜测**：映射由 AI 生成，脚本不得内置任何渠道/平台组合的字段表。
4. 不做未声明的单位换算或类型转换（如价格单位、token 数单位）；上游无可靠数据的可选字段不映射、不编造。
5. 已有映射可复用时直接使用；仅当映射缺失、用户要求重建、目标字段已不符合平台格式或源字段已不在当前缓存中时才重建。

示例（Sense → pi）：

```env
# ~/.cache/models/pi_from_sense.env
id=id
name=name
contextWindow=context_length
maxTokens=max_tokens
reasoning=reasoning
input=input
```

### 6. 批量转换全部模型

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/apply_mapping.py \
  --source ~/.cache/models/<channel>.jsonc \
  --mapping ~/.cache/models/<platform>_from_<channel>.env \
  --output /tmp/<channel>-<platform>-models.json
```

- 模型 `id` 原样保留，不允许改名或添加/去掉前缀。
- 每个模型逐字段读取，缺少某个可选源字段时省略该目标字段，而不是填默认值或猜测。
- 转换后核对：条目数量与实测小结的可用清单一致（经第 3 步实测剔除的生图/不可用模型与"渠道特定规则"版本族/精简过滤的除外）、`id` 唯一、必填字段齐全。
- 目标平台必填但源数据无法提供的字段：**中止并请用户补充**，不得编造。平台有明确默认值的可选字段可按该平台规则省略。

### 7. 渠道新增约束检查（任何新增渠道前）

**除非用户显式声明，否则不得主动添加 opencode / openrouter 渠道**。调用守卫脚本确认：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/guard_channel_add.py <channel>
```

- 输出 `OK` → 允许新增，继续第 8 步（合并写入）。
- 输出 `BLOCKED`（退出码 1）→ **立即停止**，不新增渠道，向用户说明并请其显式声明（设置 `ALLOW_NO_AUTO_ADD=1` 全放行，或 `ALLOW_NO_AUTO_ADD=<channel,...>` 仅放行指定渠道）后重试。
- 判断不区分大小写；约束只限制**新增渠道**动作，**更新已有渠道的模型不受影响**。

**Magpie 本地服务渠道**（本地电脑部署的服务，如 `127.0.0.1:3425`）：**无论是否启用都需要添加**（作为渠道存在）；**若服务未启动，除非显式指定，否则不修改该渠道的模型列表**。判定：`<PREFIX>_BASE_URL` 为本地地址（`127.0.0.1` / `localhost` / `0.0.0.0` 或内网回环）且 `/models` 或 chat 实测连接失败（如 `Connection refused`）→ 视为服务未启动：**允许创建/保留渠道但跳过模型写入**（不写 `models`），仅当用户显式指定（`MAGPIE_FORCE=1`）才写入模型。判断不区分大小写。

### 8. 备份并按平台格式合并写入

按 `references/<platform>.md` 的结构与现有配置格式编辑**用户级**配置文件：

- **新增渠道**：渠道 key 使用 `channel`；显示名未指定时使用 `channel`；`baseUrl` 写入 `<PREFIX>_BASE_URL` 的**真实值**；接口类型默认采用该平台的 OpenAI Chat Completions 兼容模式（pi 为 `api: "openai-completions"`，zcode 为 `api.type: "openai-chat-completions"`，dsh 为 `api: openai-completions`，atomcode 为 `provider = "openai-compatible"`，omp 为 `api: openai-completions`（YAML 列表），opencode 为 `package: "aisdk:@ai-sdk/openai-compatible"` + `settings.baseURL`（v2 的 `api` 字段已废弃），qoder 为 `type: "openai-compatible"` + `protocol: "openai"` + `authType: "bearer"`，且模型条目 id 字段名为 `model`）。codebuddy 无渠道层级，按模型条目写入，且 `url` **必须是完整路径**（`<PREFIX>_BASE_URL` 去尾斜杠后拼接 `/chat/completions`；详见 `references/codebuddy.md`）。
- **更新已有渠道**：以模型 `id` 为合并键 upsert——同 id 更新、新 id 追加、不产生重复；不删除本次未出现的手工模型；与本次同步无关的 provider/模型保持不变。dsh 目标还须不动 patch 文件头注释与其它无关条目（详见 `references/dsh.md`）。omp 的渠道级字段（`baseUrl`/`api`/`apiKey`/`auth`/`headers`）**已有值不动**、仅缺失或为空时补入，且 `apiKey` 保留 omp 现有环境变量名（同一渠道在 omp 里的 env 名可能与本技能前缀不同，不可覆盖）；opencode 只合并 `providers.{渠道}.models` map 并补全缺失的 `package`、不动 `settings.baseURL`/`apiKey`；qoder 只合并 `models` 数组、渠道级字段（`baseUrl`/`apiKey`/`type`/`protocol`/`authType`）不动（详见 `references/opencode.md`、`references/qoder.md`）。
- **密钥**：默认写入引用形式 `!echo -n "$<PREFIX>_API_KEY"`（平台支持时）；dsh 为 `apiKeyEnv: <PREFIX>_API_KEY`（只写环境变量名引用，**绝不写明文**）；atomcode 为 `api_key = "$<PREFIX>_API_KEY"`（TOML 环境变量引用，不落明文）；omp 为 `apiKey: <PREFIX>_API_KEY`（**环境变量名裸形式、不带 `$`、不带 `!echo`**——omp 按同名环境变量解析，抄 pi 形式会失败）；opencode 为 `settings.apiKey: "{env:<PREFIX>_API_KEY}"`（`{env:...}` 占位符，配置中不落明文）；平台明确只支持明文时（zcode、codebuddy、qoder、dbx、mimocode）写入环境变量实值，仅出现在目标配置的必要字段中，报告中只说明"密钥已配置"，含明文的文件与备份权限 `0600`。
- **备份**：每次真实写入前创建带时间戳的备份（如 `models.json.bak-YYYYMMDDHHMMSS`）；含明文密钥的备份权限设为 `0600`。目标为 DBX 时写入的是 SQLite 库（`dbx.db`），**写库前先退出 DBX 应用**以免写锁与运行时覆盖，备份为 `dbx.db.bak-YYYYMMDD`（详见 `references/dbx.md`）。
- 只写用户级全局配置，**禁止修改项目级/工作区内的配置文件**（qoder 另须避开 `<项目>/.qoder/settings.json` 与 `settings.local.json`，并按目录存在情况同时写 `~/.qoder/settings.json` 与 `~/.qoder-cn/settings.json`；omp 只写 `~/.omp/agent/models.yml`，禁止项目级）。

### 9. 写后验证

重新读取目标配置并核对：

- 文件可被平台要求的格式解析（JSON/YAML/JSONC/TOML）；
- 渠道 key、显示名、`baseUrl`、接口类型正确；
- 模型数量与本批转换结果一致、`id` 唯一、无意外重复（codebuddy 为扁平数组，`id` 全数组唯一；若存在非空 `availableModels` 须已列入本批 id；omp 用 `python3 -c "import yaml,sys;yaml.safe_load(open(sys.argv[1]))"` 校验 YAML；opencode 的 `models` 为对象 map，key 与 `modelID` 须一致；qoder 的模型条目字段集合固定为 `model`/`displayName`/`contextWindow`/`maxOutputTokens`/`capabilities`，不增删）；
- 密钥采用该平台要求的形式，且输出中不出现明文（omp 必须是裸环境变量名、opencode 必须是 `{env:...}`；qoder/dbx/codebuddy 为明文实值，核对时不得回显）。

验证失败时保留备份、报告失败原因，**不得宣称同步成功**；需要时用备份恢复。

## 渠道文档与参数 schema

| 渠道 | 官方文档 URL | 参数 schema（本地） |
|------|--------------|---------------------|
| sense / sense-ai（SenseNova） | https://platform.sensenova.cn/docs | `references/sense.schema.json` |
| ifm（IFM / MBZUAI） | https://docs.ifm.ai/#/chat-completions | `references/ifm.schema.json` |
| agnes / agnes-com（Agnes AI） | https://agnes-ai.cn/zh-Hans/docs/agnes-30-flash 、https://agnes-ai.cn/zh-Hans/docs/agnes-25-flash | `references/agnes.schema.json` |

> 渠道 key `sense`（baseUrl `token.sensenova.cn`）与 `sense-ai`（baseUrl `token.sensenova.ai`）为同一 SenseNova 渠道的国内/海外双域名，**文档与 schema 通用**（环境变量前缀仍按渠道标识推导：`SENSE_*` / `SENSE_AI_*`）；新渠道同理——同一提供商的多域名变体只建一份 `<渠道名>.schema.json`。

`references/<渠道名>.schema.json` 从渠道官方文档提取：各端点（chat/completions、models、images/generations 等）的请求/响应字段（类型、必填、默认值、枚举、说明）、模型清单（上下文/最大输出/模态/推荐采样参数）与注意事项（限流、思考模式字段差异等）。**字段映射（第 5 步）与排查参数问题时先查该文件**，不必重新抓取文档。

> **约束：新渠道文档 → schema 提取**。每当用户提供新渠道及其官方文档时，**必须**从文档中提取生成 `references/<渠道名>.schema.json`（沿用 sense 文件结构：`$source/channel/baseUrl/auth/endpoints/models/notes`）并登记到上表；JS 渲染的文档站需从页面打包资源中提取正文。字段说明须来自文档原文语义，文档未提供的信息省略、不得编造；生成后用 `python3 -m json.tool` 校验。与 `model-channel-sync` 的同渠道 schema 文件保持同内容（一处更新后同步另一处）。

## 渠道特定规则

- **Sense 渠道参数精简**：渠道 baseUrl 为 `token.sensenova.cn` / `token.sensenova.ai`（渠道 key `sense` / `sense-ai`）时，写入 pi/omp/dsh 的模型条目**不携带 `reasoning` 与 `maxTokens` 两个参数**（dsh 侧精简 `maxTokens`，`reasoningEfforts` 本就不映射），已有条目中的这两个参数在同步/清理时一并移除；`contextWindow` 等其它参数照常（按 baseUrl 主机判定，勿按渠道 key 判定）。
- **Sense 渠道版本族精简**：只保留每个系列的最新版模型（如 `sensenova-6.7-flash-lite` 和 `sensenova-6.8-flash-lite` 只保留后者）；同系列（id 含相同前缀）按版本号排序取最高。
- **生图模型不入 pi/omp**：走 `/images/generations` 端点的图片生成模型（第 3 步实测判定：chat 404 但 /models 列表存在，或 `output_modalities` 只含 `image`，如 sense 渠道的 `sensenova-u1.5-lite`）**不得写入 pi 与 omp 配置**——两平台只把配置条目当聊天模型，生图无可用路径；目标配置已有的遗留条目在同步/清理时移除。同理不写 codebuddy（只有聊天模型条目 + `supportsImages` 图片**输入**开关）、atomcode（只有聊天模型 + `supports_vision`）、qoder（模型条目字段集合固定，无生图注册路径）与 opencode（`models` 条目按聊天模型使用）。
- **Agnes 渠道只添加 flash 文本模型**：渠道 baseUrl 主机为 `api.agnes-ai.cn`（`agnes`）或 `apihub.agnes-ai.com`（`agnes-com`，国际版）时，写入清单**只保留 flash 文本模型**：id 去掉可选的 `agnes-com/` 前缀后匹配 `^agnes-\d+(\.\d+)*-flash$`（当前即 `agnes-2.5-flash`、`agnes-3.0-flash`）。`agnes-*-pro`、`*-pro-beta`、`*-pro-alpha` 以及 image/video 模型（含 `agnes-image-*-flash`、`agnes-video-*-flash`）一律不写入；**存量非 flash 条目在同步/清理时一并移除**（覆盖第 8 步"不删除本次未出现的手工模型"的默认行为）。image 只走 `/v1/images/generations`（`response_format` 须放在 `extra_body` 内），video 只走 `POST /v1/videos` 创建任务 + `GET /agnesapi?video_id=...&model_name=...` 轮询；chat 实测分别返回 400 `is an image model` / `is a video model`。报告可列 `/models` 全量并标注剔除原因，但写入清单只含上述 flash 文本模型。
- **Agnes 未上线/已废弃模型不写入**：`agnes-3.0-pro` 文档标注"即将上线"（响应仅为格式示例），`agnes-2.0-flash` 已废弃（迁移至 `agnes-2.5-flash`），均不得写入；`agnes-2.5-pro-alpha` 无独立文档页（2.5 Pro 页仅提及其开源权重），非用户显式要求不写入。
- **Agnes 上下文/输出**：只写 flash 文本模型：`agnes-2.5-flash` / `agnes-3.0-flash` 上下文 512K（524288）、最大输出 65536；pro 系列不写入，其上下文信息仅保留在 schema 中备查。
- **Agnes 思考模式字段**：OpenAI 兼容请求用 `chat_template_kwargs.enable_thinking` 开启 Thinking（不是 `reasoning_effort` / `thinking`），Anthropic Messages 请求用 `thinking.type` + `budget_tokens`（常规编码任务从 2048 起）；三套协议均可调用同一文本模型。
- **系列白名单 + 9 个月时间窗（nvidia / amd / jiutian）**：这三个渠道在同步与查看（`model_probe.py list/test`）时默认只保留 `SERIES_ALLOW` 系列：`minimax`、`mimo`、`glm`、`qwen`、`deepseek`、`kimi`、`step`、`muse`（取 id 中 model 部分开头连续字母前缀，不区分大小写：`qwen/qwen3.8-27b` → `qwen`、`DeepSeek-V4-Flash` → `deepseek`），其它系列（minicpm、gemma、moma、jiutian 等）剔除；同时剔除 `/models` 的 `created` 早于 **9 个月**前的模型，**无 `created` 数据的模型保留**（国内网关多不返回发布时间，不能据此判为过期）。`SKIP_SERIES_FILTER=1` 跳过系列过滤、`SKIP_TIME_FILTER=1` 跳过时间窗。**classifier（decision 输出）不受这两条约束**。查看（`model_probe.py list/test`）另按 id 剔除 tts / rerank / embedding / asr / whisper 等非对话模型（`/models` 缺模态字段时兜底）。实现与 `model-channel-sync` 的 `scripts/pi_cache.py` / `scripts/model_probe.py` 一致。
- **决策模型（classifier）例外**：`/models` 的 `output_modalities` 含 `decision` 的模型（如 amd 的 `d3`、`d3-flash`、`Clef`）是 classifier，**不是**多模态/非对话模型——查看时单列标注，且不受系列白名单与时间窗过滤（`model_probe.channel_rules` 豁免）；同步时 `pi_cache.filter_models` 对 `type: "classifier"` 豁免全部过滤，默认以原因「分类器」剔除（opencode/omp/qoder/zcode/dsh/codebuddy/atomcode 等目标均无 classifier 能力）。**写入位置仅限 pi provider extension**（`~/.pi/agent/extensions/*.ts`，`registerProvider` 中 `type: "classifier"` + `api: "typesafe-system-one"` + provider 级 `compat.imageInput` + `classifiers` 实现）；**不能写 `models.json`**（`modelFromJson` 忽略 `type`，只会生成为聊天模型），也**不写任何其它平台配置**。pi 内仅经 codemode `models.classify()` / 扩展 `ctx.modelRegistry.classify()` 调用，不出现在 `/model`。
- **AMD 渠道全量同步**：不区分免费/付费，同步时全量写入所有模型（受上述系列白名单与 9 个月时间窗过滤后）；**classifier（`d3` / `d3-flash` / `Clef`）除外**，只经 pi provider extension 注册。
- **模型 id 保持源渠道原样**：不得擅自添加或去掉前缀（渠道自带前缀如 `amd/deepseek-latest-flash` 原样保留）。
- **模型 displayName/name**：统一为 **`{渠道显示名} - {模型名}`** 格式（如 `NewAPI - Sense DeepSeek Latest Flash`）；模型名已含渠道名则去重。

> 上述规则与 `model-channel-sync` SKILL 的渠道特定规则一致（本次同步固化），确保单渠道更新与多平台同步行为一致。

## 平台支持


| 平台 | 用户级配置 | 参考 |
|------|-----------|------|
| pi | `~/.pi/agent/models.json`（chat/image）；`~/.pi/agent/extensions/*.ts`（classifier，仅 provider extension） | `references/pi.md` |
| omp | `~/.omp/agent/models.yml`（YAML，根对象**只接受 `providers`**；`models` 为列表、条目 `{id, name}` 起步；`apiKey` 为**环境变量名裸形式**（不带 `$`）、`baseUrl` 明文；Sense 渠道不写 `reasoning`/`maxTokens`） | `references/omp.md` |
| zcode | `~/.zcode/v2/provider_config.json` | `references/zcode.md` |
| dsh | `~/.dsh/profiles/<profile>/cordis.patch.yml`（patch 层，CLI 常规为 `web`，Electron 桌面版为 `desktop`） | `references/dsh.md` |
| codebuddy | `~/.codebuddy/models.json`（扁平 `models[]`，无渠道层级；`url` 必须含 `/chat/completions` 完整路径；仅支持 OpenAI 接口格式；`apiKey` 明文实值；热重载 1 秒防抖） | `references/codebuddy.md` |
| dbx | `dbx.db`（SQLite）的 `ai_configs` 表（每渠道一条记录，模型在 `models` 字段；`model`/`models` 与 `config_json` 双写） | `references/dbx.md` |
| atomcode | `~/.atomcode/config.toml`（TOML：`[provider_accounts.*]` + `[models."<账号id>/<模型id>"]`；`api_key` 支持 `$VAR` 引用；改后 `/reload` 生效） | `references/atomcode.md` |
| opencode | `~/.config/opencode/opencode.json`（v2：顶层 `providers`（V1 为 `provider`）、`models` 为**对象 map**、条目用 `modelID`；端点在 `settings.baseURL`（`api` 已废弃）、适配器在 `package`；`apiKey` 用 `{env:VAR}` 占位符；**默认禁止新增渠道**（第 7 步守卫）） | `references/opencode.md` |
| qoder | `~/.qoder/settings.json`（国外版）与 `~/.qoder-cn/settings.json`（国内版）的 `providers` 段（BYOK，桌面版与 CLI 共用；渠道 key 为 `qoder-custom-{UUID}`；`models` 为数组、条目 id 字段名为 `model`；`apiKey` 为**明文实值**；禁止写项目级与 `settings.local.json`） | `references/qoder.md` |

其他平台在首次使用时按官方文档确认结构并补充 `references/<platform>.md`。

## 错误处理

| 情况 | 处理 |
|------|------|
| 环境变量缺失/为空 | 停止，报告缺失变量名，不写配置 |
| `/models` 请求失败或响应异常 | 停止，保留旧缓存仅作诊断，不写目标配置 |
| 响应模型数组为空 | 视为抓取失败，不覆盖旧缓存、不写目标配置 |
| 实测全部不可用（test_models.py 退出码 1） | 停止，报告实测明细，不写目标配置 |
| 生图模型（chat 404 但 /models 存在） | 从写入清单剔除、不写入只支持聊天模型的平台（pi/omp/codebuddy/atomcode/qoder/opencode），报告中注明走 /images/generations |
| 决策模型（`output_modalities` 含 `decision`） | 不从 `models.json` 写入（会被当聊天模型）；仅在 pi 用 provider extension 注册，其它平台剔除并注明「分类器」 |
| 映射缺失/失效 | 由 AI 重新生成映射后再转换 |
| 守卫 `BLOCKED`（渠道禁止新增） | 停止，不新增渠道，请用户显式声明（`ALLOW_NO_AUTO_ADD=1` 或列表）后重试 |
| 目标必填字段无法从源数据获得 | 中止，请用户补充 |
| 写入或写后验证失败 | 报告失败，保留时间戳备份用于恢复 |

## 安全规则

- 源缓存、映射缓存、转换输出与命令日志中**不得出现 API Key**。
- 报告只说明密钥已配置及其形式，不打印明文。
- 明文密钥只允许写入目标用户级配置的必要字段；相关配置与备份切勿提交到版本库。
- 运行 Python 脚本时使用 `PYTHONDONTWRITEBYTECODE=1`，避免生成 `__pycache__`。
- **渠道新增约束**：除非用户显式声明，否则不得主动添加 opencode / openrouter 渠道（第 7 步守卫脚本强制）；更新已有渠道模型不受此限。
