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
  version: "1.3.0"
---

# 模型渠道新增与更新（上游 → 目标平台）

从上游渠道的 `/models` 接口抓取模型列表，按目标平台的配置格式新增或更新渠道及其全部模型。目标平台格式是转换权威，字段映射由执行本技能的 AI 依据语义生成，脚本只负责确定性的抓取、缓存与批量复制。

**目录结构**：
- `references/` — 各目标平台配置格式（写入前必读，按需渐进加载）
- `scripts/fetch_models.py` — 读取环境变量、请求 `/models`、原子写入源缓存
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

`环境变量检查 → /models 抓取 → 源缓存 → 读取目标格式 → AI 映射 → 批量转换 → 渠道新增约束检查 → 备份与合并 → 写后验证`

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

### 3. 读取目标平台格式

读取 `references/<platform>.md` 和用户级现有配置，确认：渠道层级、模型条目结构、必填/可选字段、接口类型名称、密钥引用能力。目标现有配置只用于识别真实字段与平台能力，不用于反向推翻目标结构。

### 4. 生成、校验或复用字段映射

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

### 5. 批量转换全部模型

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/apply_mapping.py \
  --source ~/.cache/models/<channel>.jsonc \
  --mapping ~/.cache/models/<platform>_from_<channel>.env \
  --output /tmp/<channel>-<platform>-models.json
```

- 模型 `id` 原样保留，不允许改名或添加/去掉前缀。
- 每个模型逐字段读取，缺少某个可选源字段时省略该目标字段，而不是填默认值或猜测。
- 转换后核对：条目数量与源缓存一致、`id` 唯一、必填字段齐全。
- 目标平台必填但源数据无法提供的字段：**中止并请用户补充**，不得编造。平台有明确默认值的可选字段可按该平台规则省略。

### 6. 渠道新增约束检查（任何新增渠道前）

**除非用户显式声明，否则不得主动添加 opencode / openrouter 渠道**。调用守卫脚本确认：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/guard_channel_add.py <channel>
```

- 输出 `OK` → 允许新增，继续第 7 步（合并写入）。
- 输出 `BLOCKED`（退出码 1）→ **立即停止**，不新增渠道，向用户说明并请其显式声明（设置 `ALLOW_NO_AUTO_ADD=1` 全放行，或 `ALLOW_NO_AUTO_ADD=<channel,...>` 仅放行指定渠道）后重试。
- 判断不区分大小写；约束只限制**新增渠道**动作，**更新已有渠道的模型不受影响**。

**Magpie 本地服务渠道**（本地电脑部署的服务，如 `127.0.0.1:3425`）：**无论是否启用都需要添加**（作为渠道存在）；**若服务未启动，除非显式指定，否则不修改该渠道的模型列表**。判定：`<PREFIX>_BASE_URL` 为本地地址（`127.0.0.1` / `localhost` / `0.0.0.0` 或内网回环）且 `/models` 或 chat 实测连接失败（如 `Connection refused`）→ 视为服务未启动：**允许创建/保留渠道但跳过模型写入**（不写 `models`），仅当用户显式指定（`MAGPIE_FORCE=1`）才写入模型。判断不区分大小写。

### 7. 备份并按平台格式合并写入

按 `references/<platform>.md` 的结构与现有配置格式编辑**用户级**配置文件：

- **新增渠道**：渠道 key 使用 `channel`；显示名未指定时使用 `channel`；`baseUrl` 写入 `<PREFIX>_BASE_URL` 的**真实值**；接口类型默认采用该平台的 OpenAI Chat Completions 兼容模式（pi 为 `api: "openai-completions"`，zcode 为 `api.type: "openai-chat-completions"`）。
- **更新已有渠道**：以模型 `id` 为合并键 upsert——同 id 更新、新 id 追加、不产生重复；不删除本次未出现的手工模型；与本次同步无关的 provider/模型保持不变。
- **密钥**：默认写入引用形式 `!echo -n "$<PREFIX>_API_KEY"`（平台支持时）；平台明确只支持明文时写入环境变量实值，仅出现在目标配置的必要字段中，报告中只说明"密钥已配置"。
- **备份**：每次真实写入前创建带时间戳的备份（如 `models.json.bak-YYYYMMDDHHMMSS`）；含明文密钥的备份权限设为 `0600`。
- 只写用户级全局配置，**禁止修改项目级/工作区内的配置文件**。

### 8. 写后验证

重新读取目标配置并核对：

- 文件可被平台要求的格式解析（JSON/YAML/JSONC）；
- 渠道 key、显示名、`baseUrl`、接口类型正确；
- 模型数量与本批转换结果一致、`id` 唯一、无意外重复；
- 密钥采用该平台要求的形式，且输出中不出现明文。

验证失败时保留备份、报告失败原因，**不得宣称同步成功**；需要时用备份恢复。

## 渠道特定规则

- **Sense 渠道参数精简**：渠道 baseUrl 为 `token.sensenova.cn` / `token.sensenova.ai`（渠道 key `sense` / `sense-ai`）时，写入 pi/omp 的模型条目**不携带 `reasoning` 与 `maxTokens` 两个参数**，已有条目中的这两个参数在同步/清理时一并移除；`contextWindow` 等其它参数照常（按 baseUrl 主机判定，勿按渠道 key 判定）。
- **Sense 渠道版本族精简**：只保留每个系列的最新版模型（如 `sensenova-6.7-flash-lite` 和 `sensenova-6.8-flash-lite` 只保留后者）；同系列（id 含相同前缀）按版本号排序取最高。
- **AMD 渠道全量同步**：不区分免费/付费，同步时全量写入所有模型（受系列约束过滤后）。
- **模型 id 保持源渠道原样**：不得擅自添加或去掉前缀（渠道自带前缀如 `amd/deepseek-latest-flash` 原样保留）。
- **模型 displayName/name**：统一为 **`{渠道显示名} - {模型名}`** 格式（如 `NewAPI - Sense DeepSeek Latest Flash`）；模型名已含渠道名则去重。

> 上述规则与 `model-channel-sync` SKILL 的渠道特定规则一致（本次同步固化），确保单渠道更新与多平台同步行为一致。

## 平台支持


| 平台 | 用户级配置 | 参考 |
|------|-----------|------|
| pi | `~/.pi/agent/models.json` | `references/pi.md` |
| zcode | `~/.zcode/v2/provider_config.json` | `references/zcode.md` |

其他平台在首次使用时按官方文档确认结构并补充 `references/<platform>.md`。

## 错误处理

| 情况 | 处理 |
|------|------|
| 环境变量缺失/为空 | 停止，报告缺失变量名，不写配置 |
| `/models` 请求失败或响应异常 | 停止，保留旧缓存仅作诊断，不写目标配置 |
| 响应模型数组为空 | 视为抓取失败，不覆盖旧缓存、不写目标配置 |
| 映射缺失/失效 | 由 AI 重新生成映射后再转换 |
| 守卫 `BLOCKED`（渠道禁止新增） | 停止，不新增渠道，请用户显式声明（`ALLOW_NO_AUTO_ADD=1` 或列表）后重试 |
| 目标必填字段无法从源数据获得 | 中止，请用户补充 |
| 写入或写后验证失败 | 报告失败，保留时间戳备份用于恢复 |

## 安全规则

- 源缓存、映射缓存、转换输出与命令日志中**不得出现 API Key**。
- 报告只说明密钥已配置及其形式，不打印明文。
- 明文密钥只允许写入目标用户级配置的必要字段；相关配置与备份切勿提交到版本库。
- 运行 Python 脚本时使用 `PYTHONDONTWRITEBYTECODE=1`，避免生成 `__pycache__`。
- **渠道新增约束**：除非用户显式声明，否则不得主动添加 opencode / openrouter 渠道（第 6 步守卫脚本强制）；更新已有渠道模型不受此限。
