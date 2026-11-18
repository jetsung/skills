---
name: model-channel-sync
description: >-
  管理 AI 模型渠道（provider）配置：①提取真正可用的免费/零价模型（抓取 → 筛选 → 连通性实测 → 剔除不可用 → 给出结论）；
  ②以 pi 等平台配置为基准，同步/更新渠道、模型、APIKEY 到多个 agent 工具（pi、zcode、dsh、omp、opencode、mimocode、qoder、codebuddy、dbx、atomcode 等）的配置文件。
  凡用户提到"获取/提取/列出 XX 渠道免费模型"、"从价格判断免费模型"、"查价格为零的模型"、"有哪些免费模型可用"、
  "给 XX 渠道加免费模型"、"这个免费模型能用吗/测试一下"、"把模型更新到 pi/omp/opencode/mimocode/dsh/zcode/qoder/codebuddy/dbx/atomcode"、
  "以 pi 为基准更新 XX 渠道"、"同步渠道/模型/APIKEY 到 XX"、"更新 XX 的 APIKEY"、
  "同步到 mimocode / 覆盖 mimocode 的提供商 / pi 同步到 mimocode"时，都应使用此技能。
  支持配置文件中所有 OpenAI 兼容渠道（openrouter、kilo、opencode、newapi、nvidia、atomgit 等）。
compatibility: Requires curl, python3 (with PyYAML), and network access to provider APIs.
metadata:
  version: "1.11.0"
---

# 模型渠道配置管理（免费提取与多工具同步）

本技能管理**AI 模型渠道配置**：从任意渠道提取**真正可用**的免费/零价模型，并将渠道、模型、密钥同步到多个 agent 工具的配置文件。核心价值：很多模型看似免费（带 `free` 标签或定价为 0），但实际因地区限制、鉴权失败、上游故障而不可用。技能完成「抓取 → 筛选 → 实测 → 结论 → 可选写入/同步多工具」的完整闭环。
## 术语定义

本技能涉及两个容易混淆的概念，先明确：

**平台（platform）**：AI 编码**工具**本身，指读写的配置文件所属软件，如 pi、omp（Oh My Pi）、opencode、mimocode、dsh、zcode、qoder、codebuddy、dbx、atomcode。平台负责**消费**模型（调用模型做编码/对话），本身不提供模型。

**渠道（channel / provider）**：**模型提供商**，含中转站（如 openrouter、newapi、kilo、ds2api），是平台配置文件 `providers`（或等价字段）下的某个 key。渠道负责**提供**模型（`baseUrl` + `apiKey` 指向的 AI 服务），一个平台可接入多个渠道。

> 关系：**一个平台接入多个渠道，每个渠道提供一批模型**。本文所有"渠道"均指模型提供商；"平台"均指 pi/omp 等工具。同步方向通常为**以 pi 平台配置为基准 → 同步到其它平台**，同步的是**渠道及其模型**（同一渠道可被多个平台共用）。

**目录结构**：
- `scripts/` — 各工具同步脚本（幂等，自动备份+断言校验）、上游免费模型提取脚本 `fetch_free.py`，与模型清单/可用性实测脚本 `model_probe.py`（`list <渠道>` 拉 /models 完整清单并标注免费判定与生图剔除；`test <渠道> [模型id ...]` 逐个 chat 实测并按 429 可用/404 生图/403 套餐不可用规则输出小结；渠道配置默认读 pi，也可 `--base-url/--api-key` 指定）
- `references/` — 各平台配置结构详细参考（按需加载，写配置前先读对应文件）

## 触发时机

当用户希望了解或配置某渠道的免费模型、或把模型同步到工具配置时使用，典型表述：
- "从 XX 获取免费模型列表供我选择"
- "从价格中判断哪些是免费模型"
- "XX 渠道有哪些免费模型可用"
- "给 pi/omp 的 XX 渠道添加免费模型"
- "把这个免费模型更新到 opencode / pi / omp / dsh"
- "这个免费模型能用吗 / 测试一下这个模型"
- "以 pi 平台的配置为基准，更新 XX 平台的提供商及模型"
- "同步渠道/模型/APIKEY 到 XX"
- "更新 XX 的 APIKEY"
- "把模型同步到 mimocode / 覆盖 mimocode 的 provider"

## 前置步骤：确认渠道、筛选方式与目标工具（必须）

**开工前，先向用户确认三件事**（不要擅自假设）：

### 1. 目标渠道（channel）

渠道是 pi 配置文件 `~/.pi/agent/models.json` 中 `providers` 下的某个 key，例如：
`sense`、`amd`、`ds2api`、`openrouter`、`newapi`、`agnes`、`cloudflare`、`atomgit`、`kilo`、`nvidia`、`opencode`。

从配置读取该渠道的 `baseUrl` 和 `apiKey`。若用户未指明，默认 `openrouter`。

### 2. 筛选方式（criteria）

不同渠道判断"免费"的方式不同，必须向用户确认：

| 方式 | 说明 | 适用渠道示例 |
|------|------|--------------|
| `price=0` | 按模型定价为 0 筛选 | openrouter（有 `pricing` 字段）、及其他提供定价的渠道 |
| `free-tag` | 按模型 id 含 `:free` / `-free` / `/free` | openrouter、kilo、opencode |
| `keyword` | 按模型 id/name 含用户指定关键词（如 `free`） | newapi（`-free-latest`）等 |
| `auto` | 价格=0 **或** free 标签 | 通用 |

**降级规则**：若渠道 API 不提供 `pricing` 字段（多数非 openrouter 渠道没有），`price=0` 无法准确判断，此时自动退化为 `free-tag` 或 `keyword`，并明确告知用户。

### 3. 目标工具（target，写入时才需要）

若用户要把提取结果写入配置，需确认写入哪些工具：

| 工具 | 配置文件 | 详细参考 |
|------|----------|----------|
| pi | `~/.pi/agent/models.json`（chat/image）；`~/.pi/agent/extensions/*.ts`（classifier，仅 provider extension） | `references/pi.md` |
| omp (Oh My Pi) | `~/.omp/agent/models.yml` | `references/omp.md` |
| opencode | `~/.config/opencode/opencode.json` | `references/opencode.md` |
| mimocode | `~/.config/mimocode/mimocode.jsonc` | `references/mimocode.md` |
| dsh (DeepSeek Harness) | `~/.dsh/profiles/web/cordis.patch.yml`（profile patch 层） | `references/dsh.md` |
| zcode | `~/.zcode/v2/provider_config.json` | `references/zcode.md` |
| qoder | `~/.qoder/settings.json`（国外版）与 `~/.qoder-cn/settings.json`（国内版） | `references/qoder.md` |
| codebuddy | `~/.codebuddy/models.json`（CLI 与 IDE 共用；扁平 `models[]`，`url` 须含 `/chat/completions` 完整路径，仅 OpenAI 接口格式） | `references/codebuddy.md` |
| dbx | `dbx.db`（SQLite）的 `ai_configs` 表，数据目录见 `references/dbx.md` | `references/dbx.md` |
| atomcode | `~/.atomcode/config.toml`（TOML：`[provider_accounts.*]` + `[models.*]`） | `references/atomcode.md` |
| 其他 | 用户提供路径与结构 | 遵循该工具现有格式 |

> 默认查询/提取只需渠道+筛选方式，写入配置时才确认目标工具。
> qoder 是同一软件的国外版（`~/.qoder`）与国内版（`~/.qoder-cn`），结构相同；**按目录存在情况同步，都存在则都同步**。
> 注意：dsh 的渠道配置不来自 pi 的 `models.json`，读取 baseUrl/apiKey 应以 `~/.dsh/profiles/<profile>/cordis.patch.yml` 为准（CLI 启动默认 profile 为 `web`；Electron 桌面版为 `desktop`，该 profile 由桌面应用专管）；zcode 同理。
> atomcode 的配置是 **TOML**（`~/.atomcode/config.toml`），采用「账号 + 模型剖面」新式结构；密钥只写 `$VAR` 形式引用（不落明文），改动后需 `/reload` 或重启才生效；详见 `references/atomcode.md`。

## 依赖

- 目标渠道的 `baseUrl` 与 `apiKey`（通常从 pi 配置文件读取；若写入目标是 dsh，则从 `~/.dsh/profiles/<profile>/cordis.patch.yml` 读取渠道 `baseURL` 与 `apiKeyEnv`，**再按 `apiKeyEnv` 取环境变量实值**——dsh 的 patch 文件不含明文密钥）
- `curl` 和 `python3`

## pi 数据缓存（一次提取并验证，多平台共用）

各 `sync-pi-to-*.py` 脚本**不直接读 pi**，也不各自做渠道检查，而是统一经 `scripts/pi_cache.py` 读取缓存 `~/.cache/model-channel-sync/pi-models.json`。**缓存即检查结果**——渠道可用性验证在缓存生成时一次性完成：

- **提取即检查（两段式实测）**：生成缓存时对每个渠道做两步验证（apiKey 从 pi 解析为实值，候选模型取 pi 渠道自带模型 id，最多试 5 个）：
  1. **端点探测**：调 `GET {baseUrl}/models`——HTTP 200 且返回 `data` 数组（允许空）→ 端点可达并取实时模型 id 列表；HTTP 405 / 无 data → 可达但无模型列表；其它 HTTP 错误 / 连接失败 / 非 JSON → **渠道不可用**
  2. **chat 实测**：用候选模型调 `POST {baseUrl}/chat/completions` 发最小真实请求（`max_tokens:8`）——**HTTP 200 且有 `choices` → 可用**；HTTP 429 限流（`rate limit` / `inference exceeds tpm/rpm limit`）→ **可用**（临时限额，模型/渠道存在）；401/403 鉴权失败、候选模型全部 400/404/5xx（模型停用/失效）、连接失败 → **不可用**

  > **为什么必须 chat 实测**：部分网关的 `/models` 端点**不鉴权**——无密钥也返回模型列表，仅凭 HTTP 200 会误判可用。chat 实测才能证明密钥有效与模型可推理。`poolside`（模型全部 deactivated）、`hyper`（401 密钥无效）即由此暴露。
  > 候选模型由 pi 渠道自带列表提供（`/models` 返回空/405 时仍可实测）；两者都无时退化为仅端点探测，reason 注明"未做 chat 实测"。

- **渠道不通**（任一实测失败，**不含 HTTP 429 限流**）→ 该渠道**不写入缓存**；同步脚本从缓存取数时自然跳过此渠道，不创建 provider、不写密钥、不合并模型
- **HTTP 429 限流**（`Too Many Requests` / `rate limit` / `inference exceeds tpm/rpm limit`）→ **视为可用**（临时限额，模型/渠道存在，按可用渠道处理）
- **可用且 /models 返回模型列表** → 原装数据入缓存，并记入 `models_api[渠道] = [实时模型 id 列表]`
- **可用但无 /models 接口**（HTTP 405、端点不返回 data 列表等）→ 记入 `no_models_api` 列表；同步时**直接以 pi 写死的模型列表为准**，不做实时过滤
- **中转站渠道**（`pi_cache.py` 的 `FORCE_NO_MODEL_FILTER`，当前为 openrouter、nvidia）：判定依据是 pi 模型条目的 **`vendor` 字段值（不区分大小写）** 命中名单（渠道 key 命中也兜底生效），如某渠道模型的 `vendor` 为 `Openrouter` 即视为中转站。此类渠道 `/models` 可读但模型列表与 pi 不一一对应（聚合/改名），**按 no_models_api 方式处理**——同步时直接以 pi 写死的模型列表为准（不做失效过滤），**参数值（contextWindow/maxTokens/input 等）仍从缓存原装数据取**
- **模型失效过滤**：同步时 `/models` 可读的渠道只添加实时列表中仍存在的模型——pi 有但实时缓存中已不存在的模型**不添加**（`pi_cache.filter_models`，剔除的在报告中注明）
- **只同步文本模型**：pi 模型条目 `input` 字段缺省默认 `["text"]`（视为文本模型）；`input` 存在时必须包含 `text` 才同步——`["text","image"]` 的视觉模型照常同步，纯 `image`/`ocr` 等不支持文本输入的模型**不同步**（`pi_cache.is_text_model`，剔除的在报告中注明）。上游免费模型提取（`fetch_free.py`）同步剔除 id 含 `ocr` 的模型
- **系列白名单 + 9 个月时间窗**（nvidia / amd / jiutian）：同步时剔除系列不在 `pi_cache.SERIES_ALLOW`（`minimax`/`mimo`/`glm`/`qwen`/`deepseek`/`kimi`/`step`/`muse`/`hy`）的模型，并剔除 `/models` 的 `created` 早于 9 个月前的模型；**无 `created` 数据的模型保留**。`SKIP_SERIES_FILTER=1` / `SKIP_TIME_FILTER=1` 可分别跳过，剔除项在报告中注明
- **生图模型不入 pi/omp**：走 `/images/generations` 端点的图片生成模型（`/models` 的 `output_modalities` 只含 `image`，或 chat 实测 404 `model is not found`——生图模型不支持 chat，404 即判定信号，无需探测 images 端点）**禁止写入 pi（`~/.pi/agent/models.json`）与 omp（`~/.omp/agent/models.yml`）**——两平台把 `models.json`/`models.yml` 里的条目一律当聊天模型（api 只有聊天类取值，schema 无字段可声明 image 类型；pi 的生图调用 `models.generateImages` 仅认内置 catalog 注册的 image 模型，如 openrouter 的 `google/gemini-2.5-flash-image`），生图模型写进去选中即报错，毫无可用路径。pi 已有的生图遗留条目在同步/清理时**移除**（报告中注明）；如确需使用生图模型，只能写 provider extension，不属于配置文件同步范围。其它平台同样不写：codebuddy 只有聊天模型条目（`supportsImages` 是图片**输入**开关）、atomcode 只有聊天模型 + `supports_vision`、zcode/dsh/qoder/dbx/omp 的条目也一律按聊天模型处理，故生图/视频/音频输出模型由各同步脚本经 `pi_cache.filter_models` 统一剔除
- **决策模型（classifier）例外**：`/models` 的 `output_modalities` 含 `decision` 的模型（如 amd 的 `d3`、`d3-flash`、`Clef`）是 **classifier（决策模型）**，不是多模态/非对话模型——`model_probe.py` 会单列标注（`classifier` 列 + 小结），且**不受系列白名单与 9 个月时间窗过滤**（`channel_rules` 豁免）；`pi_cache.filter_models` 对 `type: "classifier"` 条目豁免失效/文本/系列/时间四类过滤，默认同步时以原因「分类器」剔除（其它平台无 classifier 能力，atomcode 亦然——它只有文本聊天模型 + `supports_vision` 布尔），`keep_classifier=True` 时原样保留。**写入位置仅限 pi provider extension**（`~/.pi/agent/extensions/*.ts`）：`registerProvider` 中声明 `type: "classifier"` + `api: "typesafe-system-one"`、provider 级 `compat.imageInput`（AMD 为 `"images"`，`sendImageOptInHeader: false`）、并按 `api` 提供 `classifiers` 实现；**不能写 `models.json`**——`provider-composer.modelFromJson` 忽略条目 `type`，只会生成为聊天模型（选中即报错）。pi 内只能经 codemode 的 `models.classify()` 或扩展 `ctx.modelRegistry.classify()` 调用，**不出现在 `/model`**。
- **数据权威顺序**：渠道与模型**以 pi 为准**（哪些渠道、哪些模型），但**数据内容以缓存为准**（缓存是检查后的快照：不可用渠道已被剔除、失效模型已被标记）
- **原装数据**：可用渠道的 providers 段原样保存（含 contextWindow/maxTokens/input/cost 等，不裁剪），支持参数的平台直接取用
- **失效策略**：pi 文件 mtime 变化即重新提取（**重新做渠道检查**）；`PI_CACHE_TTL`（秒）强制过期重提；`python3 scripts/pi_cache.py` 手动刷新并查看检查结果（可用/不可用/无 /models 接口渠道清单）
- 手动单渠道自检：`python3 scripts/channel_check.py <渠道名> <baseUrl> <apiKey> ...`（两段式：/models 端点探测 + chat 实测；无候选模型时退化为仅端点探测）
- **探测优先用 curl，urllib 仅兜底**：部分服务器（如 `apihub.agnes-ai.com`）对 Python urllib 的 TLS 握手**稳定挂起**（OpenSSL 3.5.9 与服务器不兼容），`channel_check.py` 的 `_probe_models`/`_probe_chat` 已重构为 **curl 主探测（`_curl_get`/`_curl_post`）+ urllib 兜底**（curl 不可用/异常时回退 urllib）。修改探测代码时保持此顺序：**先 curl 后 urllib**，勿颠倒。

## 各平台模型配置官方文档（速查）

| 平台 | 官方文档 URL |
|------|--------------|
| pi | https://pi.dev/docs/latest/models |
| omp (Oh My Pi) | https://omp.sh/docs/custom-models |
| opencode | https://opencode.ai/v2/docs/models 、https://opencode.ai/v2/docs/providers 、https://opencode.ai/v2/docs/migrate-v1 |
| mimocode | https://mimo.xiaomi.com/mimocode/config.json （schema） |
| dsh（DeepSeek Harness） | https://deepseek-harness.github.io/deepseek-harness/guide/providers ；中文源：https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/providers.zh.md （字段全集见 config-catalog 的 `dsh-llm-pi-ai`/`PiAiCompatProfile`） |
| zcode | GitHub 源码：https://github.com/zai-org/ZCode （schema 入口：`packages/provider/src/config/provider-data-schema.ts`、`packages/provider/src/config/rule-data-schema.ts`、`packages/shared/src/model-config.ts`） |
| qoder | —（providers 段为 BYOK 存储，以 `references/qoder.md` 为准） |
| codebuddy | CLI：https://www.codebuddy.cn/docs/cli/models ；IDE：https://www.codebuddy.cn/docs/ide/Features/models （同一 `~/.codebuddy/models.json`，字段以两份文档并集为准，差异见 `references/codebuddy.md`） |
| atomcode | https://atomcode.atomgit.com/docs/zh/configuration.html ；源码：https://atomgit.com/atomgit_atomcode/atomcode.git （结构定义 `crates/atomcode-config/src/config/provider.rs`、`provider_preset.rs`） |

> 需要核对某平台最新配置结构时，直接抓取对应 URL（注意：omp 文档页面为 JS 渲染，普通抓取只返回空壳，需从页面 JS 打包资源中提取文本；pi/codebuddy 可直接抓取）。

## 渠道（模型提供商）文档与参数 schema（速查）

| 渠道 | 官方文档 URL | 参数 schema（本地） |
|------|--------------|---------------------|
| sense / sense-ai（SenseNova） | https://platform.sensenova.cn/docs | `references/sense.schema.json` |
| ifm（IFM / MBZUAI） | https://docs.ifm.ai/#/chat-completions | `references/ifm.schema.json` |
| agnes / agnes-com（Agnes AI） | https://agnes-ai.cn/zh-Hans/docs/agnes-30-flash 、https://agnes-ai.cn/zh-Hans/docs/agnes-25-flash | `references/agnes.schema.json` |
| maritaca（Maritaca AI · Sabiá / S5） | https://docs.maritaca.ai/pt/api/openai-compatibilidade （另参 /pt/api/comeco-rapido、/pt/responses-api、/pt/modelos） | `references/maritaca.schema.json` |

> 渠道 key `sense`（baseUrl `token.sensenova.cn`）与 `sense-ai`（baseUrl `token.sensenova.ai`）为同一 SenseNova 渠道的国内/海外双域名，**文档与 schema 通用**；新渠道同理——同一提供商的多域名变体只建一份 `<渠道名>.schema.json`。
> maritaca 官方文档为葡萄牙语 Docusaurus 站点，代码块是 Python / cURL 双标签页，普通抓取只返回 Python 标签——cURL 标签里的**完整端点 URL** 需从页面 HTML 反转义后提取（`/api/v1/responses`、`/api/chat/completions`）；模型清单在 `/pt/modelos` 文档页而非 API 端点。

`references/<渠道名>.schema.json` 从渠道官方文档提取：各端点（chat/completions、models、images/generations 等）的请求/响应字段（类型、必填、默认值、枚举、中文说明）、模型清单（上下文/最大输出/模态/推荐采样参数）与注意事项（限流、思考模式字段差异等）。**写调用代码、排查参数错误、判断模型可用端点前先查该文件**，不必重新抓取文档。

> **约束：新渠道文档 → schema 提取**。每当用户提供新渠道及其官方文档时，除常规同步配置外，**必须**从文档中提取生成 `references/<渠道名>.schema.json`（沿用 sense 文件结构：`$source/channel/baseUrl/auth/endpoints/models/notes`），并登记到上表；文档为 JS 渲染时按平台文档速查的提示从打包资源中提取正文。字段说明须来自文档原文语义，文档未提供的信息省略、不得编造；生成后用 `python3 -m json.tool` 校验。

## 工作流程（提取免费模型）

### 第 1 步：读取渠道配置

- **pi**：从 `~/.pi/agent/models.json` 读取 `baseUrl` 和 `apiKey`；`apiKey` 形如 `!echo -n "$ENV_VAR"`，需解析出环境变量名并取值（详见 `references/pi.md`）
- **dsh**：从 `~/.dsh/profiles/<profile>/cordis.patch.yml` 读取——顶层是 Cordis patch **数组**，先按 `id == 'llm-pi-ai'` 定位条目，再取 `config.providers.{渠道}` 的 `baseURL` 与 `apiKeyEnv`，密钥经 `apiKeyEnv` 取环境变量实值（**文件内无明文密钥**，详见 `references/dsh.md`）
- **zcode**：从 `~/.zcode/v2/provider_config.json` 读取渠道 `config.api.baseUrl` 与 `config.access.apiKey`（明文；详见 `references/zcode.md`）
- **qoder**：从 `~/.qoder/settings.json`（或 `~/.qoder-cn`）读取 `providers.{渠道key}` 的 `baseUrl` 与 `apiKey`（明文；详见 `references/qoder.md`）
- **atomcode**：从 `~/.atomcode/config.toml` 的 `[provider_accounts.<账号id>]` 读取 `base_url` 与 `api_key`（`api_key` 多为 `$VAR` 形式，按环境变量取值；模型侧在 `[models."<账号id>/<模型id>"]`，详见 `references/atomcode.md`）

### 第 2 步：调用 /models 接口抓取模型

**优先用脚本**：`python3 scripts/model_probe.py list <渠道名>`（自动从 pi 解析 baseUrl/apiKey，输出含创建时间、模态、上下文、定价与免费判定的完整清单；纯图/视频/音频输出与 OCR 模型自动剔除并列出）。渠道不在 pi 配置中时用 `--base-url <url> --api-key <key|ENV名>`。

OpenAI 兼容渠道通常支持 `GET {baseUrl}/models`。若返回 `data` 数组则解析；若接口不支持或报错，向用户说明并改用其他方式（如从配置文件的 `models` 列表读取）。

```bash
curl -s "$BASE_URL/models" -H "Authorization: Bearer $API_KEY" | python3 -m json.tool
```

### 第 3 步：按用户指定的方式筛选

**通用筛选脚本模板（按需调整字段）：**
```bash
curl -s "$BASE_URL/models" -H "Authorization: Bearer $API_KEY" | python3 -c "
import json,sys
from datetime import datetime
data=json.load(sys.stdin)
models=data.get('data',[])
print('总模型数:', len(models))
# 收集所有免费模型
free_models = []
for m in sorted(models, key=lambda x: x['id']):
    mid=m['id']
    p=m.get('pricing',{})
    prompt=p.get('prompt','0'); comp=p.get('completion','0')
    free_tag=':free' in mid or '-free' in mid or '/free' in mid
    zero=prompt in ('0','0.0','0.000000') or comp in ('0','0.0','0.000000')
    # 按 auto 方式示例：zero 或 free_tag 命中
    if zero or free_tag:
        created = m.get('created', 0)
        created_str = datetime.fromtimestamp(created).strftime('%Y-%m-%d %H:%M') if created else '未知'
        desc = m.get('description','')[:100]  # 取前100字符作为简述
        arch = m.get('architecture',{})
        desc += f\" (架构: {arch.get('name',arch.get('architecture','未知'))})\" if arch else ''
        free_models.append({'id': mid, 'name': m.get('name',mid), 'created': created,
                           'created_str': created_str, 'free_tag': free_tag, 'zero': zero,
                           'desc': desc[:200]})  # 最多200字符
# 按创建时间从新到旧排序
free_models.sort(key=lambda x: x['created'], reverse=True)
print('免费模型总数:', len(free_models))
print('---')
for m in free_models:
    source = '价格0非free标签' if m['zero'] and not m['free_tag'] else 'free标签' if m['free_tag'] and not m['zero'] else '价格0+free标签'
    print(f\"{m['created_str']} | {m['id']} | {source} | {m['desc'][:80]}\")
"
```

> **注意**：渠道无 `pricing` 字段时 `p` 为空 dict，`prompt`/`comp` 取默认 `'0'` 会误判，此时必须改用 `free-tag`/`keyword` 并告知用户。

### 第 4 步：连通性测试

**优先用脚本**：`python3 scripts/model_probe.py test <渠道名> [模型id ...]`（不传 id 则测 /models 全部；内置判定规则：200 有 choices/content/reasoning → 可用，429 → 可用（临时限流），404 且 /models 存在 → 生图模型不入 pi/omp，403 region/token plan → 不可用；输出逐个明细 + 小结分类）。

对筛选出的每个候选模型逐个调用 chat/completions 接口实测，剔除不可用（**HTTP 429 限流视为可用**）：

```bash
for mid in "候选1" "候选2"; do
  echo "=== $mid ==="
  # -w "%{http_code}" 取状态码；429 限流视为可用（模型存在，临时限额）
  code=$(curl -s -o /tmp/resp.json -w "%{http_code}" "$BASE_URL/chat/completions" \
    -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$mid\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":5}")
  if [ "$code" = "429" ]; then echo "可用（429 rate-limited，临时限额）"; cat /tmp/resp.json; else cat /tmp/resp.json; fi
  echo
done
```

**解读响应（重要）：**
- 有 `choices` 且 `message.content` 或 `message.reasoning` 有值 → **可用**（推理模型 content 为 null 但 reasoning 有值也算可用）
- HTTP 429（`rate limit` / `Too Many Requests` / `inference exceeds tpm/rpm limit`）→ **可用**（临时限额/限流，模型存在，仅需限频后重试；不得剔除）
- `error.message` 含 "not available in your region" → **地区限制，不可用**
- `error` 表示鉴权失败 / 上游错误 → **不可用**（如 401/403/404/503 等；**429 除外**）
- chat 返回 404 `model is not found` 但 `/models` 列表中存在该 id → 判定为**生图模型**（只走 `/images/generations`，不支持 chat，无需二次探测）：不入 pi/omp（见渠道特定规则），有 `output_modalities` 字段时可用来交叉确认
- 音频/视频模型（如 `google/lyria-*`）通常受地区限制且不适合编程，直接标不可用

### 第 5 步：输出报告

按模板输出（**必须完整列出所有模型，不省略**）：

```
# {渠道} 免费模型清单（按创建时间从新到旧）

## 筛选方式：{price=0 / free-tag / keyword / auto}
## 免费模型总数：N 个

---

| 序号 | 创建时间 | 模型ID | 来源类型 | 描述 |
|------|----------|--------|----------|------|
| 1 | YYYY-MM-DD HH:MM | model/id | 价格0+free | 完整描述文本（包含架构、用途、参数等） |
| 2 | ... | ... | ... | ...
...
| N | ... | ... | ... | ...

---

## 完整列表（详细版）

【1】YYYY-MM-DD HH:MM | 来源类型
    模型ID: model/id
    架构: [架构类型]
    描述: {完整描述，不截断}

【2】...
    ...
```

**关键要求：**
- 表格版可截断描述（最多150字符），但**完整列表版必须展示全部模型的完整描述**
- 若描述被 API 截断（含"..."），保持原样输出，不要伪造内容
- 编号从1到N，连续无遗漏
- 每个模型独立一段，便于阅读

## 写入多个工具配置（可选）

用户选择写入时，按工具分别处理。各工具结构不同，**修改格式须与文件中原有条目一致**。写入前先读对应参考文件：

| 写入目标 | 必读参考 | models 结构 | apiKey 处理 |
|----------|----------|-------------|-------------|
| pi | `references/pi.md` | `providers.{渠道}.models` 数组 `{id, name}`，可补 maxTokens/contextWindow/reasoning/input/cost | 保留 `!echo -n "$VAR"` 形式 |
| omp | `references/omp.md` | `providers.{渠道}.models` YAML 列表 `{id, name}` | env 变量名**裸形式**（不带 `$`），保留 omp 现有引用（env 名可能不同，如 omp kilo 用 `NVIDIA_API_KEY`，不可覆盖） |
| opencode | `references/opencode.md` | v2：`providers.{渠道}.models` 对象 map（key=id，value `{modelID, name, family}`）；provider 缺 `package` 时补 `aisdk:@ai-sdk/openai-compatible`（`settings` 存 apiKey/baseURL） | 保留 `{env:XXX}` 占位符 |
| mimocode | `references/mimocode.md` | **不从 pi 直写**；经 opencode 中转后 `provider` 整块覆盖 | **写死明文实值**（解析 `{env:VAR}` / `!echo` 占位符） |
| dsh | `references/dsh.md` | patch 条目 `id: llm-pi-ai` → `config.providers.{渠道}.models` 列表（条目 `{id, name?, contextWindow?, maxTokens?, input?}`，脚本同步 pi 原装参数；`reasoningEfforts`/`compat` 不在脚本范围） | **不写密钥**：只用 `apiKeyEnv` 引用环境变量（明文另有 `.credentials.yaml`，见下） |
| zcode | `references/zcode.md` | 规则式（`personalModelIds`/`modelOrder` + `providerModelRules`） | **写死明文实值**（不支持 env 引用） |
| qoder | `references/qoder.md` | `providers.{qoder-custom-{UUID}}.models` 数组（id 字段名为 `model`） | **写死明文实值**（渠道顶层） |
| codebuddy | `references/codebuddy.md` | 扁平 models 数组（无渠道层级，每模型独立条目）；**仅支持 OpenAI Chat Completions**，`url` 必须是完整路径（`/chat/completions` 结尾） | **写死明文实值**（现有 `${VAR}` 条目一并转换；IDE 侧只认明文） |
| dbx | `references/dbx.md` | 每渠道一条 `ai_configs` 记录（name=渠道显示名；模型列表在 `config_json.models` 字符串数组） | **写死明文实值**（写入 `config_json.apiKey`） |
| atomcode | `references/atomcode.md` | TOML 新式结构：`[provider_accounts.<账号id>]`（provider/base_url）+ `[models."<账号id>/<模型id>"]`（account/model/display_name/context_window/supports_vision）；文本级追加（环境无 TOML 写入库），原文件逐字保留 | 只写 `$VAR` 形式引用（从 pi 的 `!echo -n "$VAR"` 提取变量名），**不落明文密钥** |

**共同规则：**
- 只写**用户级（全局）**配置，**禁止修改项目级/工作区内的配置文件**（pi/omp/opencode/dsh/zcode/qoder/codebuddy/dbx/atomcode 全部适用）
- 只合并/新增模型条目，保留已有条目不变；同步为**合并式（只增不删）**，上游下架的模型不会自动移除，需清理时手动处理（**mimocode 例外**：经 opencode 覆盖，整块替换）
- **完全替换模式（`--replace`）**：加 `--replace` 时以 pi 为基准**完全替换**目标平台渠道/模型——① 删除 pi 没有的渠道（`KEEP_CHANNELS` 指定保留，默认 `{'magpie'}` 保留渠道但跳过模型更新）；② 删除 pi 有的渠道中 pi 没有的模型；③ 自动创建 pi 有但目标没有的渠道；④ 断言放行（允许删除而非只增）。当前已支持：`sync-pi-to-omp.py`、`sync-pi-to-opencode.py`（均含自动创建新渠道）；zcode/qoder/codebuddy/dbx/dsh 的替换用结构化重写脚本完成（见下方"完全替换（结构化）"）。**未加 `--replace` 默认仍是合并式**。atomcode 只有合并式（TOML 无写入库，脚本走文本级追加，未实现 `--replace`）。
- 若 API 返回的模型包含 maxTokens、contextWindow 等参数字段，同步写入时一并更新到配置文件中（字段映射见各参考文件；渠道特定规则中注明的除外，如 Sense 渠道不写 `reasoning`/`maxTokens`）
- 渠道级字段（baseURL/kind/compat/npm 等）：已有值不更新，仅目标缺失/为空时补入（opencode v2 的 `package` 缺失时补默认适配器 `aisdk:@ai-sdk/openai-compatible`；mimocode 的 `npm` 缺失时补 `@ai-sdk/openai-compatible`）

### 多工具全量同步（pi 为基准）

按目标工具选脚本（均在 `scripts/` 下，幂等可重复执行，自动备份+断言校验；执行前按需修改脚本顶部路径/别名变量）：

```bash
python3 scripts/sync-pi-to-opencode.py
python3 scripts/sync-pi-to-opencode.py --replace   # 完全替换（删渠道/模型，自动新建）
python3 scripts/sync-pi-to-dsh.py              # 默认 profile=web；--profile <名> / --dry-run
python3 scripts/sync-pi-to-omp.py
python3 scripts/sync-pi-to-omp.py --replace     # 完全替换（删渠道/模型，自动新建）
python3 scripts/sync-pi-to-zcode.py
python3 scripts/sync-pi-to-qoder.py
python3 scripts/sync-pi-to-codebuddy.py
python3 scripts/sync-pi-to-dbx.py          # 写入 DBX ai_configs 表；加 --dry-run 只打印计划不写库
python3 scripts/sync-pi-to-mimocode.py     # 两段流水线：pi → opencode → 覆盖 mimocode
python3 scripts/sync-pi-to-atomcode.py     # TOML 文本级追加；ATOMCODE_CONFIG=<副本路径> 可试运行
```

**完全替换（结构化）**：zcode/qoder/codebuddy/dbx/dsh 的 sync 脚本**未加 `--replace`**（合并式），完全替换用**结构化重写脚本**（按平台写临时脚本，yaml/JSON/SQLite 结构化处理，先副本测试再应用真实文件）：
- **dsh**：yaml 结构化重写（保留头部注释与顶层条目，改 `llm-pi-ai` 条目的 `config.providers`，重建的模型条目同样生成 id + name/contextWindow/maxTokens/input 参数行）——dsh 无特殊 YAML 标签（`!!js` 仅注释），可安全结构化重写；替换脚本用 `DSH_TEST` 环境变量指向测试副本，真实路径 `~/.dsh/profiles/web/cordis.patch.yml`
- **zcode**：JSON 结构化（`providerRules`/`providerOrder`/`providerModelRules` 联动删除与重建）；渠道按 `providerName` 规范化匹配 pi；新渠道 providerId 用 baseURL 域名主体（`api.ifm.ai`→`ifm`，`llm.asfd.cn`→`asfd`）
- **qoder/qoder-cn**：JSON 结构化（`providers` 按 baseUrl 去尾斜杠匹配；新渠道 key=`qoder-custom-{UUID}`，模型条目含 `model`/`displayName`/`capabilities`）；`QODER_TEST` 指向测试副本目录（`:` 分隔）
- **codebuddy**：扁平 `models[]` 按 `vendor`（渠道显示名）匹配；**agnes-com/sense-ai 的模型 id 加渠道前缀**（`agnes-com/`、`sense-ai/`）避免与 agnes/sense 的 id 冲突（vendor 分别用 `AgnesCom`/`Sense AI`）
- **dbx**：`ai_configs` 表 0 行时直接跑 `sync-pi-to-dbx.py` 全量新建（每渠道一条配置）；替换前先备份 `dbx.db.bak-replace-*`
- **通用**：替换前手动备份目标文件（`.bak-replace-YYYYMMDD-*`）；用副本先验证（渠道/模型数、无重复 id、字段完整、JSON/YAML 有效），确认后应用真实文件

**mimocode 专用流水线（先 opencode 后覆盖，必须按序）**：mimocode 的 `provider` 与 opencode 同构，**不从 pi 直写**。目标是把 mimocode 的提供商**清空后用 opencode 的 `provider` 整块覆盖**（非合并）；**密钥写明文**（mimocode 不认 `{env:VAR}` 占位符，脚本自动解析环境变量实值）：

```bash
python3 scripts/sync-pi-to-mimocode.py              # ① pi→opencode 合并 ② opencode→mimocode 覆盖
python3 scripts/sync-opencode-to-mimocode.py        # 只做②（opencode 已是最新时）
python3 scripts/sync-opencode-to-mimocode.py --dry-run
```

细节与字段差异见 `references/mimocode.md`。覆盖后 mimocode 独有模型字段（如 `cachePromptTTL`）会丢失，需保留时在 opencode 源补。

**上游免费渠道（kilo / openrouter）**：这两个渠道同步到 **zcode / dsh / qoder** 时**不走 pi models 基准**，改由 `scripts/fetch_free.py` 从上游 `GET {baseUrl}/models` 提取**免费模型**，须同时满足：
1. **免费**：id 含 `:free`/`-free`/`/free` 标签，或 `pricing.prompt`/`completion` 均为 0（含临时免费）
2. **最近一年内更新**：`created` 时间戳在一年内；无时间数据的剔除（如 kilo 的 `kilo-auto/free` 聚合入口）
3. **上下文**：`context_length`（顶层或 `top_provider` 内）若存在则必须 >100K；无 context 数据的保留（如 opencode 的 /models 无此字段）
4. 剔除图像/视频/音频类（lyria/image/video 等）

- **opencode 渠道不同步**（SKIP_CHANNELS）：其上游价格数据不正确，无法可靠判定免费
- 提取结果缓存 `~/.cache/model-channel-sync/free-{渠道}.json`（1 小时）；上游请求失败回退上次缓存，无缓存则回退 pi models 并在报告中注明
- 同步到 **opencode 工具**（`sync-pi-to-opencode.py`）与 **omp / pi** 时维持 pi 基准不变
- qoder 归属判定豁免：这两个渠道的上游免费模型（含 short id）归对应渠道 provider 所有，不参与跨渠道迁出判定

### 渠道特定规则

- **不得主动添加 opencode / openrouter 渠道**（除非用户显式声明）：同步脚本在目标平台（omp/zcode/qoder/dbx 等）**无对应渠道时禁止自动新建**这两个渠道的 provider，仅在用户显式声明添加（`ALLOW_NO_AUTO_ADD=1` 或渠道在 `ALLOW_NO_AUTO_ADD` 列表）时放行。**存量/已有 provider 的模型更新不受限**，仅限制"新建渠道"动作；opencode/dsh 脚本本身无自动新建（无匹配即跳过），codebuddy 为扁平结构无渠道层级，均不受影响。实现：`pi_cache.no_auto_add()` 统一守卫（`NO_AUTO_ADD_CHANNELS`），各脚本新建分支调用。
- **Magpie 本地服务渠道**（本地电脑部署的服务，如 `127.0.0.1:3425`）：**无论是否启用都需要添加**（作为渠道存在，如 omp 的 `magpie`）；**若服务未启动，除非显式指定，否则不修改该渠道的模型列表**。判定：本地地址（`127.0.0.1` / `localhost` / `0.0.0.0` 或内网回环）且 `/models` 或 chat 实测连接失败（如 `Connection refused`）→ 视为服务未启动，同步时**保留渠道但跳过模型更新**（不新增/不删除/不改模型列表），仅当用户显式指定（如 `MAGPIE_FORCE=1` 或 `--with-magpie`）才强制更新。magpie 渠道**不在 pi 基准**（pi 的 `models.json` 无此渠道），故 pi→omp 等同步天然不会动它；此规则约束**任何可能触碰本地渠道的同步路径**。
- **系列白名单 + 9 个月时间窗（nvidia / amd / jiutian）**：这三个渠道在同步与查看（`model_probe.py list/test`）时默认只保留 `SERIES_ALLOW` 系列：`minimax`、`mimo`、`glm`、`qwen`、`deepseek`、`kimi`、`step`、`muse`、`hy`（腾讯混元，如 `hy3`、`hy4-preview`）（取 id 中 model 部分开头连续字母前缀，不区分大小写：`qwen/qwen3.8-27b` → `qwen`、`DeepSeek-V4-Flash` → `deepseek`），其它系列（minicpm、gemma、moma、jiutian 等）剔除；同时剔除 `/models` 的 `created` 早于 **9 个月**前的模型，**无 `created` 数据的模型保留**（国内网关多不返回发布时间，不能据此判为过期）。`SKIP_SERIES_FILTER=1` 跳过系列过滤、`SKIP_TIME_FILTER=1` 跳过时间窗。**classifier（decision 输出）不受这两条约束**。查看（`model_probe.py list/test`）另按 id 剔除 tts / rerank / embedding / asr / whisper 等非对话模型（`/models` 缺模态字段时兜底）。实现：`pi_cache.filter_models()`（同步）、`model_probe.channel_rules()`（查看）
- **AMD 渠道全量同步**：不区分免费/付费，同步时全量写入所有模型（受上述系列白名单与 9 个月时间窗过滤后）；**classifier（`d3` / `d3-flash` / `Clef`）除外**——它们不进 `models.json`，只经 provider extension 注册（见下条）
- **AMD 决策模型（classifier）**：`d3`、`d3-flash`、`Clef` 的输出是 `decision`，只能走 pi 的 codemode `models.classify()`。落盘位置 `~/.pi/agent/extensions/amd-classifier.ts`：独立 provider `amd-classifier`（**不能并入 `amd`**——extension 的 `models` 会整体替换该 provider 的全部模型，吞掉 `models.json` 的聊天模型），三个条目均 `type: "classifier"`、`api: "typesafe-system-one"`、`input: ["text","image"]`、`contextWindow: 32768`、`cost` 全 0，provider 级 `compat: { imageInput: "images", sendImageOptInHeader: false }`（AMD 用 Clef 风格 data URL 数组），`classifiers["typesafe-system-one"]` 自带 `POST {baseUrl}/systemone` 实现（扩展内不能 import pi-ai 子路径，需用全局 `fetch` + `options.apiKey`）。调用：`models.getModelOfType("classifier", "amd-classifier", "d3")`。启用 codemode：`settings.json` 的 `defaultTools` 含 `+codemode`
- **Sense 渠道版本族精简**：只保留每个系列的最新版模型（如 `sensenova-6.7-flash-lite` 和 `sensenova-6.8-flash-lite` 只保留后者）；同系列（id 含相同前缀）按版本号排序取最高
- **Sense 渠道参数精简**：渠道 baseUrl 为 `token.sensenova.cn` / `token.sensenova.ai`（渠道 key `sense` / `sense-ai`）时，写入 pi/omp/dsh 的模型条目**不携带 `reasoning` 与 `maxTokens` 两个参数**（dsh 侧精简 `maxTokens`，`reasoningEfforts` 本就不映射），pi/omp 已有条目中的这两个参数在同步/清理时一并移除；`contextWindow` 等其它参数照常（按 baseUrl 主机判定，勿按渠道 key 判定；omp/dsh 侧由 `sync-pi-to-omp.py` / `sync-pi-to-dsh.py` 自动执行该精简）
- **Agnes 渠道只添加 flash 文本模型**：渠道 baseUrl 主机为 `api.agnes-ai.cn`（`agnes`）或 `apihub.agnes-ai.com`（`agnes-com`，国际版）时，写入清单**只保留 flash 文本模型**：id 去掉可选的 `agnes-com/` 前缀后匹配 `^agnes-\d+(\.\d+)*-flash$`（当前即 `agnes-2.5-flash`、`agnes-3.0-flash`）。`agnes-*-pro`、`*-pro-beta`、`*-pro-alpha` 以及 image/video 模型（含 `agnes-image-*-flash`、`agnes-video-*-flash`）一律不写入；**存量非 flash 条目在同步/清理时一并移除**（覆盖第 8 步"不删除本次未出现模型"的默认行为）。image 只走 `/v1/images/generations`（`response_format` 须放在 `extra_body` 内），video 只走 `POST /v1/videos` 创建任务 + `GET /agnesapi?video_id=...&model_name=...` 轮询；chat 实测分别返回 400 `is an image model` / `is a video model`。报告可列 `/models` 全量并标注剔除原因，但写入清单只含上述 flash 文本模型
- **Agnes 未上线/已废弃模型不写入**：`agnes-3.0-pro` 文档标注"即将上线"（响应仅为格式示例），`agnes-2.0-flash` 已废弃（迁移至 `agnes-2.5-flash`），均不得写入；`agnes-2.5-pro-alpha` 无独立文档页（2.5 Pro 页仅提及其开源权重），非用户显式要求不写入
- **Agnes 上下文/输出**：只写 flash 文本模型：`agnes-2.5-flash` / `agnes-3.0-flash` 上下文 512K（524288）、最大输出 65536；pro 系列不写入，其上下文信息仅保留在 schema 中备查
- **Agnes 思考模式字段**：OpenAI 兼容请求用 `chat_template_kwargs.enable_thinking` 开启 Thinking（不是 `reasoning_effort` / `thinking`），Anthropic Messages 请求用 `thinking.type` + `budget_tokens`（常规编码任务从 2048 起）；三套协议均可调用同一文本模型
- **Maritaca（Sabiá / S5）渠道**：渠道 key `maritaca`，baseUrl `https://chat.maritaca.ai/api`（结尾是 `/api` 不是 `/v1`）。官方主推 **Responses API**（cURL 完整路径 `https://chat.maritaca.ai/api/v1/responses`），Chat Completions 仍可用（`https://chat.maritaca.ai/api/chat/completions`）——文档内路径口径不一致（Responses 页对比表另标相对路径 `/v1/responses`、`/v1/chat/completions`，而 SDK base_url 只到 `/api`），写调用代码或排查 404 前先查 `references/maritaca.schema.json`，勿臆断路径。免费模型只有 `S5-free` / `s5-free`（限时优惠、仅文本、固定限流、无 Batch/Flex/内置工具），按 `free-tag` 命中 `-free` 后仍须实测。模型 id 有大小写与多个别名（`S5`/`s5`、`sabia-4-2026-01-06`、`sabia-4-small`、`sabiazim-4` 等），**保留原样勿改前缀**；`-br-sp` 后缀为巴西境内数据驻留变体（成本 +30%）；schema `retired` 段列出的停用模型不得写入。官方文档**未提供 `GET /models` 端点说明**，模型清单以 `/pt/modelos` 页面为准，`model_probe.py list` 接入此渠道前需先实测 `/models` 是否存在，不可假设有实时模型列表。**pi 接入必须设 `compat: {"supportsStore": false}`**：maritaca 的 `/api/chat/completions` 与 `/api/v1/responses` 都用 FastAPI/Pydantic `extra=forbid` 严格校验请求体，禁止 `store` 字段（连 `store=false` 也拒，是字段本身被禁），报 422 `extra fields not permitted`（`loc:["body","store"]`）。注意 **`api: "openai-completions"` 一样会中招**——pi 的 `openai-completions` 实现在 `compat.supportsStore` 为真时会在请求体加 `store: false`（`pi-ai/dist/api/openai-completions.js`），而该字段默认 **auto-detected from URL**，不在 pi catalog 的自定义 provider 会被判为 `true`；`openai-responses` 更是天然带 `store`。实测：带 `store` → 422，去掉 → 200，而 `max_completion_tokens` / `stream_options.include_usage` / `stream:true` / `temperature` 均被接受，故**只需关掉 `supportsStore` 这一个开关**，`api` 与 `baseUrl` 都不用改
- **模型筛选**：openrouter/opencode 渠道只补**免费模型**（id 含 `:free`/`-free`/`/free`），其它渠道全量同步
- **生图模型不入 pi/omp**：走 `/images/generations` 端点的图片生成模型（`output_modalities` 只含 `image`，或 chat 实测 404 `model is not found`，如 sense 渠道的 `sensenova-u1.5-lite`）**不得写入 pi 与 omp 的配置文件**，pi 已有的遗留条目在同步/清理时移除——两平台只把配置条目当聊天模型，生图模型无任何可用路径（依据与判定细节见「pi 数据缓存」的同一规则条目）。codebuddy / atomcode 同样不写（前者只有聊天条目 + `supportsImages` 图片输入开关，后者只有聊天模型 + `supports_vision`），统一由各 `sync-pi-to-*.py` 经 `pi_cache.filter_models` 剔除
- **模型 displayName/name**：统一为 **`{渠道显示名} - {模型名}`** 格式（如 `NewAPI - Sense DeepSeek Latest Flash`）；模型名已含渠道名则去重（如 amd 的 `AMD DeepSeek V4 Flash` → `AMD - DeepSeek V4 Flash`）
- **模型 id 保持 pi 原样**：不得擅自添加或去掉前缀（渠道自带前缀如 `amd/deepseek-latest-flash` 原样保留）
- **qoder 默认模型版本族升级**：同族模型存在更高版本时，`model` 字段自动取同族最高版本（族键/版本号提取规则见 `references/qoder.md`）

### 写入后校验

- JSON：`python3 -m json.tool`
- YAML：`python3 -c "import yaml;yaml.safe_load(open(...))"`
- 各同步脚本自带断言校验：只允许 models 新增、apiKey 更新与 baseURL/kind 空值补充

> **是否写入、写入哪些工具由用户决定，不要擅自修改任何配置文件。**

## 注意事项（Gotchas）

- **开工前必须确认渠道、筛选方式和目标工具**，不要擅自假设。
- 不要只依赖 `free` 标签，若渠道提供定价字段，用价格=0 判断更完整；渠道没有定价字段时要退化到 `free-tag`/`keyword` 并明确告知用户。
- 不要跳过连通性测试，很多"免费"模型实际不可用；报告给用户的免费清单必须是**实测可用**的，不可用的一律列入剔除原因。
- 各工具结构差异易错点：
  - dsh 的 models 条目以 `id` 必填，可带 `name`/`contextWindow`/`maxTokens`/`input` 参数行
    （`reasoningEfforts`/`compat` 不在脚本写入范围），路径是 Cordis patch 数组中 `id: llm-pi-ai`
    条目的 `config.providers.{渠道}`（`baseURL` 全大写），**顶层是列表不是映射**，不要与 pi 的
    `providers.{渠道}` 混淆；patch 文件含文件头注释与其它无关条目。**常规增量插入只能文本级**
    （禁止 `yaml.safe_dump` 整篇重写会破坏格式）；但**完全替换可安全结构化重写**——dsh 无特殊 YAML
    标签（`!!js` 仅出现在注释），用 `yaml.safe_load` 读入、改 `llm-pi-ai.config.providers`、
    `yaml.safe_dump` 重写时**保留头部注释**（前导 `#` 行）与顶层条目即可，已实测验证
  - dsh 的 profile：CLI 恒需指定 profile（`dsh web` 即 `--profile web`）；**Electron 桌面版**
    专属 profile 为 `desktop`（由桌面应用专管，dsh CLI 拒绝 boot 它，但 patch 文件可直接读写）；
    同步时目标文件不存在报"找不到配置"时，先确认该机器用的是 Web/TUI 启动还是桌面版，按
    `ls ~/.dsh/profiles/` 选对 `--profile`
  - **dsh 不写明文密钥**：provider 凭据字段是 `apiKeyEnv`（环境变量名），明文存 `$DSH_HOME/.credentials.yaml`（0600），patch 里**不应出现** `apiKey:` 明文；密钥缺失报 `MISSING_CREDENTIAL` 时走「模型页重存密钥」或「导出环境变量」，不要把明文写进 patch。同步脚本只动 `models`，不读不写任何密钥值
  - zcode 的 `access.apiKey`/qoder 的顶层 `apiKey` 均为**明文实值**，不支持任何 env 引用形式；zcode 渠道条目与模型条目字段集合**固定**，不可添加额外字段
  - qoder 的 id 字段名为 `model`（非 pi/dsh 的 `id`），`baseUrl` 顶层小写 l；渠道 key 为 `qoder-custom-{UUID}`，每渠道独立 provider + 独立密钥 + 独立模型
  - omp 的 `apiKey` 是 env 变量名裸形式（不带 `$`），与 pi 的 `!echo -n "$VAR"`、opencode 的 `{env:XXX}` 均不同；`baseUrl` 必须是**明文 URL**（omp 不解析 `{env:...}` 占位符，那是 opencode 语法）；pi 中存在但 omp 无对应的渠道**自动创建 provider**（`baseUrl` 明文、`api` 从 pi、`apiKey` 从 pi 的 `!echo -n "$VAR"` 提取 env 变量名裸形式）
  - zcode 的 `api.type: anthropic-messages` 渠道无 `/models` 端点，模型列表从 `personalModelIds` 读取
- **mimocode 走 opencode 中转，不做 pi 直写映射**；`sync-pi-to-mimocode.py` 必须先跑完 `sync-pi-to-opencode.py` 再覆盖。覆盖是**整块替换 provider**（只增不删规则对 mimocode 不适用）；**密钥必须明文**——`{env:VAR}`/`!echo` 占位符写入前解析为实值（优先级：env 实值 > 目标已有明文 > 空；与 zcode/qoder 同级）。`mimocode.jsonc` 可能含注释/尾逗号，解析须走 JSONC 宽容读取（脚本已内置）。
- 环境变量名正则须含数字（`[A-Z0-9_]+`）；长脚本用 heredoc/独立脚本文件传给 python3，**不要用 bash 双引号 `-c "..."`**（会吞掉 `\$`/`\"` 转义导致正则失效）。
- 同步/写入前先做幂等核对（缺失比对），0 缺失时无写入，避免无意义重写文件；写回前备份、写回后对比备份断言只动了目标字段。
- 写入明文密钥后报告**绝不回显密钥内容**，只报告长度/变化状态。
- 写入明文密钥的配置文件（zcode/qoder/codebuddy/dbx/mimocode）切勿提交到版本库。
- dsh / pi / opencode / omp 只写密钥引用（环境变量名），明文另有存放——dsh 在 `$DSH_HOME/.credentials.yaml`，
  该文件含明文密钥，同样切勿提交或外发；patch 与 settings 文件本身不含明文，可正常入库。
- **dbx 是 SQLite 数据库而非配置文件**：写库前先退出 DBX 应用（避免写锁与运行时覆盖）；写库前自动备份 `dbx.db.bak-YYYYMMDD`；数据目录定位（`DBX_DATA_DIR` 或平台默认路径）见 `references/dbx.md`；`is_default` 一律不改动，默认配置由用户在 DBX 设置中手动指定。
