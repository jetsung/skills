---
name: model-channel-sync
description: >-
  管理 AI 模型渠道（provider）配置：①提取真正可用的免费/零价模型；②以 pi 等平台配置为基准，同步/更新渠道、模型、APIKEY 到多个 agent 工具（zcode、dsh、pi、omp、opencode、qoder 等）的配置文件。
  凡是用户提到"获取/提取/列出/查看 XX 渠道免费模型"、"从价格判断免费模型"、"查价格为零的模型"、"有哪些免费模型可用"、
  "给 XX 渠道加免费模型"、"这个免费模型能用吗/测试一下"、"把模型更新到 pi/omp/opencode/dsh"、
  "以 pi 为基准更新 XX 渠道"、"同步渠道/模型/APIKEY 到 XX"、"更新 XX 的 APIKEY"时，都应使用此技能。
  技能通用性强：支持配置文件中所有 OpenAI 兼容渠道（openrouter、kilo、opencode、newapi、nvidia、atomgit 等）。
  提取场景需用户指定：①目标渠道，②筛选方式（按价格=0 / free 标签 / 关键词等），流程为抓取 → 筛选 → 连通性实测 → 剔除不可用 → 给出结论；同步场景需指定源与目标工具，流程为匹配渠道 → 合并模型 → 更新密钥 → 写回校验。
  若 API 返回的模型包含 maxTokens、contextWindow 等参数字段，同步写入时会一并更新到配置文件中。
---

# 模型渠道配置管理（免费提取与多工具同步）

本技能管理**AI 模型渠道配置**：从任意渠道提取**真正可用**的免费/零价模型，并将渠道、模型、密钥同步到多个 agent 工具的配置文件。核心价值：很多模型看似免费（带 `free` 标签或定价为 0），但实际因地区限制、鉴权失败、上游故障而不可用。技能完成「抓取 → 筛选 → 实测 → 结论 → 可选写入/同步多工具」的完整闭环。

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
- **pi**：`~/.pi/agent/models.json`
- **omp**：`~/.omp/agent/models.yml`
- **opencode**：`~/.config/opencode/opencode.json`
- **dsh（DeepSeek Harness）**：`~/.dsh/settings.yaml`
- **zcode（ZCode）**：`~/.zcode/v2/provider_config.json`
- **qoder（Qoder，同一软件的国外版与国内版，同步目标）**：配置目录为 `~/.qoder`（国外版）与 `~/.qoder-cn`（国内版），两目录下 `settings.json` 结构完全相同（`providers` 段，schema 见「qoder 配置」章节）。**同步目标检测：哪个目录存在就同步哪个；两个都存在则两个都同步，不再区分 qoder/qoder-cn/qodercli/qoderclicn**
- 其他工具：让用户提供配置文件路径与结构

> 默认查询/提取只需渠道+筛选方式，写入配置时才确认目标工具。
> 注意：dsh 的渠道配置并不来自 pi 的 `models.json`，其结构与 pi 不同（见「第 1 步」和「dsh」章节），读取 baseUrl/apiKeyEnv 时应以 `~/.dsh/settings.yaml` 为准；zcode 同理，见「第 1 步」和「zcode」章节。

## 依赖

- 目标渠道的 `baseUrl` 与 `apiKey`（通常从 pi 配置文件读取；若写入目标是 dsh，则从 `~/.dsh/settings.yaml` 读取）
- `curl` 和 `python3`

## 各平台模型配置官方文档（速查）

| 平台 | 配置文件 | 官方文档 URL |
|------|----------|--------------|
| pi | `~/.pi/agent/models.json` | https://pi.dev/docs/latest/models |
| omp (Oh My Pi) | `~/.omp/agent/models.yml` | https://omp.sh/docs/custom-models |
| opencode | `~/.config/opencode/opencode.json` | https://opencode.ai/docs/models 、https://opencode.ai/docs/providers |
| dsh（DeepSeek Harness） | `~/.dsh/settings.yaml` | https://deepseek-harness.github.io/deepseek-harness/guide/providers |
| zcode | `~/.zcode/v2/provider_config.json` | —（无官方文档，以本 SKILL 结构说明为准） |
| qoder（Qoder，同一软件的国外版/国内版，**同步目标**） | `~/.qoder/settings.json`（国外版）与 `~/.qoder-cn/settings.json`（国内版），结构相同；**按目录存在情况同步，都存在则都同步** | —（providers 段为 BYOK 存储，无对应官方文档，以本 SKILL「provider 条目 schema 基准」为准） |
| codebuddy | `~/.codebuddy/models.json` | https://www.codebuddy.cn/docs/cli/models |

> 需要核对某平台最新配置结构时，直接抓取对应 URL（注意：omp 文档页面为 JS 渲染，普通抓取只返回空壳，需从页面 JS 打包资源中提取文本；pi/codebuddy 可直接抓取）。

## 工作流程

### 第 1 步：读取渠道配置

**pi 配置**：从 `~/.pi/agent/models.json` 读取目标渠道的 `baseUrl` 和 `apiKey`。注意 `apiKey` 形如 `!echo -n "$ENV_VAR"`，需解析出环境变量名并取值。

```bash
# 示例：openrouter
BASE_URL="https://openrouter.ai/api/v1"
API_KEY="$OPENROUTER_API_KEY"
```

**dsh 配置**：若目标是 dsh，则从 `~/.dsh/settings.yaml` 读取，结构为 `llm-pi-ai.providers.{渠道}`，字段为 `displayName`、`apiKeyEnv`（环境变量名，非 `!echo` 形式）、`api`、`baseURL`、`models`：

```bash
# 示例：dsh 的 newapi
BASE_URL=$(python3 -c "import yaml;print(yaml.safe_load(open('~/.dsh/settings.yaml'))['llm-pi-ai']['providers']['newapi']['baseURL'])")
API_KEY_VAR=$(python3 -c "import yaml;print(yaml.safe_load(open('~/.dsh/settings.yaml'))['llm-pi-ai']['providers']['newapi']['apiKeyEnv'])")
API_KEY="${!API_KEY_VAR}"  # 按环境变量名取值
```

**zcode 配置**：若目标是 zcode，则从 `~/.zcode/v2/provider_config.json` 读取，结构为 `config.providerConfigRules.providerRules[]`（规则数组，每条 `{providerId, providerName, config}`）。渠道 key（`providerId`）为 `builtin:xxx`（内置渠道）或域名主体（自定义渠道，即 baseURL 域名去掉子域名与顶级后缀，如 `https://api.tokenrouter.com/v1` → `tokenrouter`、`https://developer.amd.com.cn/...` → `amd`；同主体不同 TLD 时带顶级后缀消歧，如 `agnes-ai-cn`/`agnes-ai-com`，详见「schema 要点」）。渠道 `config` 字段固定为 `group`（`standard-personal`）、`access: {type: "api-key", apiKey}`（**明文 key**）、`api: {type: "anthropic-messages"|"openai-chat-completions", baseUrl}`、`personalModelIds[]`、`modelOrder[]`——**字段集合固定，不可添加额外字段**（无 enabled/source/models）。模型列表在 `config.modelConfigRules.providerModelRules[]`（每条 `{modelId, config: {enabled: true}, providerId}`），不在渠道内：

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

**渠道匹配方法（pi → zcode）**：zcode 的渠道 key（`providerId`）是域名主体/`builtin:xxx`，与 pi 的渠道名不同，需按 `providerName` 字段匹配。匹配前先规范化（小写并去除非字母数字）再比较；规范化后仍不一致的用显式别名（如 pi 的 `cloudflare-workers-ai` 规范化后是 `cloudflareworkersai`，zcode 的 `CloudFlare AI` 规范化后是 `cloudflareai`，需手动映射）。pi 的 `apiKey` 形如 `!echo -n "$ENV_VAR"`，提取环境变量名时正则须含数字：`r'!echo -n "\$([A-Z0-9_]+)"'`（变量名可能是 `DS2API_API_KEY`、`V2EX_API_KEY` 这类含数字的形式）。

**qoder 配置**：若目标是 qoder，则从配置目录读取，结构为 `providers.{渠道key}`（国外版目录 `~/.qoder`、国内版目录 `~/.qoder-cn`，两者 `settings.json` 结构完全相同；**同步时按目录存在情况处理——哪个存在同步哪个，两个都存在则两个都同步**），渠道 key 为 `qoder-custom-{UUID}`。字段为 `displayName`、`baseUrl`（渠道顶层、**小写 l**）、`apiKey`（**明文 key**）、`type`/`protocol`/`authType`、`model`（当前选中模型）、`models`（**数组**，元素含 `model`/`displayName`/`contextWindow`/`maxOutputTokens`/`capabilities`）：

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

### 第 2 步：调用 /models 接口抓取模型

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

对筛选出的每个候选模型逐个调用 chat/completions 接口实测，剔除不可用：

```bash
for mid in "候选1" "候选2"; do
  echo "=== $mid ==="
  curl -s "$BASE_URL/chat/completions" \
    -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$mid\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":5}"
  echo
done
```

**解读响应（重要）：**
- 有 `choices` 且 `message.content` 或 `message.reasoning` 有值 → **可用**（推理模型 content 为 null 但 reasoning 有值也算可用）
- `error.message` 含 "not available in your region" → **地区限制，不可用**
- `error` 表示鉴权失败 / 上游错误 → **不可用**
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
- 表格版可截断描述（最多150字符），但**完整列表版必须展示全部22个模型的完整描述**
- 若描述被 API 截断（含"..."），保持原样输出，不要伪造内容
- 编号从1到N，连续无遗漏
- 每个模型独立一段，便于阅读

## 写入多个工具配置（可选）

用户选择写入时，按工具分别处理。各工具结构不同，**修改格式须与文件中原有条目一致**：

### pi → `~/.pi/agent/models.json`
`providers.{渠道}.models` 是**数组**，元素为 `{id, name}`；若 API 返回了 `maxTokens`、`contextWindow`、`reasoning`、`input`、`cost` 等字段，一并写入：
```json
{
  "id": "stealth/ox-alpha",
  "name": "Stealth OX Alpha (Free)",
  "maxTokens": 4096,
  "contextWindow": 128000
}
```
**字段映射（API 响应 → pi models.json）**：
| API 字段 | pi 字段 | 说明 |
|----------|---------|------|
| `id` | `id` | 模型标识符 |
| `name` | `name` | 可读标签 |
| `max_tokens` / `maxTokens` | `maxTokens` | 最大输出 token 数 |
| `context_length` / `contextWindow` | `contextWindow` | 上下文窗口大小 |
| `reasoning` | `reasoning` | 是否支持推理 |
| `input` | `input` | 输入类型，如 `["text"]` 或 `["text","image"]` |
| `cost` | `cost` | 计费信息 `{input, output, cacheRead, cacheWrite}` |

写入时以 pi 现有配置结构为准，仅合并/新增模型条目，保留已有条目不变。

### omp → `~/.omp/agent/models.yml`
`providers.{渠道}.models` 是 **YAML 列表**：
```yaml
- id: stealth/ox-alpha
  name: Stealth OX Alpha (Free)
```

### opencode → `~/.config/opencode/opencode.json`
`provider.{渠道}.models` 是**对象（map）**，key 为 `{family}/{id}` 或 `{id}`，value 为 `{id, name, family}`：
```json
"openrouter/stealth-ox-alpha-free": {
  "id": "stealth-ox-alpha-free",
  "name": "openrouter/stealth-ox-alpha-free",
  "family": "openrouter"
}
```
> opencode 的模型 key/name 通常复用渠道中的完整模型 id，具体以 opencode.json 现有 provider 的 models 结构为准（可能为 0 条，需参考同文件的 other provider 结构）。

#### opencode 配置结构（官方文档 https://opencode.ai/docs/models / https://opencode.ai/docs/providers）

- 配置文件 `~/.config/opencode/opencode.json`（支持 JSONC），`$schema: "https://opencode.ai/config.json"`；内置 75+ 提供商（经 AI SDK + [Models.dev](https://models.dev) 目录），凭据经 `/connect` 存于 `~/.local/share/opencode/auth.json`
- **模型引用格式**：完整 id 为 `provider_id/model_id`；`provider_id` 是配置中 `provider` 对象的键名，`model_id` 是 `provider.models` 的键名
- **provider 级字段**：
  - `options.baseURL`：覆盖该 provider 的端点（代理/自建网关用）
  - `models`：对象 map，key 为模型 id，value 为模型条目（`{id, name, family}`，另可含下述 options/variants）
  - `blacklist`：`[模型id]`，从 `/models` 选择器隐藏指定模型；`whitelist`：只保留列出模型；两者可组合（先 whitelist 收窄再 blacklist 剔除）
- **模型条目 `options`**（全局请求选项）：
  - OpenAI 类：`reasoningEffort`（`none`~`xhigh`）、`textVerbosity`、`reasoningSummary`、`include: ["reasoning.encrypted_content"]`
  - Anthropic 类：`thinking: { type: "enabled", budgetTokens: 16000 }`
- **`variants`（变体）**：同一模型多套配置而不建重复条目——`models.{id}.variants.{变体名}` 内放 options 同款字段；内置变体：Anthropic `high`/`max`（思考预算），OpenAI `none`/`minimal`/`low`/`medium`/`high`/`xhigh`，Google `low`/`high`；变体可设 `disabled: true` 停用；`variant_cycle` 快捷键切换
- **默认模型**：顶层 `"model": "provider_id/model_id"`；启动加载优先级：`--model` 标志 > 配置 `model` 字段 > 上次使用的模型 > 第一个可用模型

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "opencode/gpt-5.1-codex",
  "provider": {
    "openai": {
      "options": { "baseURL": "https://my-proxy.example.com/v1" },
      "blacklist": ["gpt-5-legacy"],
      "models": {
        "gpt-5": {
          "options": { "reasoningEffort": "high" },
          "variants": {
            "low": { "reasoningEffort": "low" },
            "fast": { "disabled": true }
          }
        }
      }
    }
  }
}
```
> 同步脚本只合并 `provider.{渠道}.models` map（含各条目的 options/variants），不动 `options.baseURL` 等已有渠道字段。

### dsh → `~/.dsh/settings.yaml`
`llm-pi-ai.providers.{渠道}.models` 是 **YAML 列表**，元素为**仅含 `id`**（无 name），且整体结构为 `llm-pi-ai.providers.{渠道}`：
```yaml
llm-pi-ai:
  providers:
    {渠道}:
      displayName: {渠道}
      apiKeyEnv: {环境变量名}   # 如 NEWAPI_API_KEY
      api: openai-completions
      baseURL: {baseUrl}
      models:
        - id: stealth/ox-alpha
        - id: another/free-model
```
> dsh 的 models 元素**只有 `id`**（不带 name），且 provider 用 `displayName`/`apiKeyEnv`/`baseURL`（注意大小写，`baseURL` 是 URL 全大写）。写入时**只更新 models 列表**，保留原 provider 的其它字段（displayName/apiKeyEnv/api/baseURL）不变，并遵循文件原有格式。

#### dsh 配置结构（官方文档 https://deepseek-harness.github.io/deepseek-harness/guide/providers）

dsh 的模型提供方配置在 `$DSH_HOME/settings.yaml`（即本 SKILL 所用的 `~/.dsh/settings.yaml`）的 `llm-pi-ai.providers` 段；Web UI「设置 → 模型」写入的就是这份文件。模型变更**下一次请求即生效，无需重启**。密钥本体存于 `$DSH_HOME/.credentials.yaml`，settings 只保留凭据引用。

- **添加提供方**（Web UI）：内置提供方（id 如 `anthropic`、`openai`、`moonshotai`、`zai`）只需密钥；自定义提供方需**小写 Provider ID**（永久，请求/会话/凭据引用都用它，重命名=新建+删除）、基础 URL、API 协议、凭据、至少一个模型。**一个提供方只用一种协议**：`openai-completions` / `openai-responses` / `anthropic-messages`，网关两种协议并存需建两个提供方
- **模型探测**：「获取可用模型」按表单当前地址/协议/密钥调用 OpenAI 兼容 `GET /models`；失败或列表为空时手动填模型 id 即可
- **模型条目字段**（手动录入模型默认按纯文本、无推理等级，需在 settings.yaml 显式声明）：
  - `id`（必填）、`input`（`[text, image]`，省略/空列表则沿用目录或回退路由 `defaultInput`，未知模态被拒绝）
  - `reasoningEfforts`：声明推理等级菜单，值为协议上 `reasoning_effort` 的写法（如 `max: xhigh` 可重命名）；`off` 留空 = 不发送该参数；设 `reasoningEfforts: false` 去掉内置模型的等级
  - `compat`：模型级兼容覆盖，逐字段胜出路由级
- **路由（provider）级字段**：
  - `apiKeyEnv`（环境变量名）、`api`（协议）、`baseURL`、`displayName`、`models`
  - `defaultInput`：模态回退值（默认 `[text]`，是回退不是覆盖）；内置提供方无 `models` 列表，用 `modelOverrides`（以模型 id 为键）
  - `reasoning`：会话未选等级时的默认推理等级
  - `compat`：路由级默认兼容开关，最常用两项——`supportsDeveloperRole: false`（系统提示词不用 `developer` 角色，很多网关拒绝）与 `maxTokensField: max_tokens`（不用 `max_completion_tokens`）
- **DeepSeek 特殊项**：默认思考的模型（OpenAI 兼容网关后的 DeepSeek V4）需 `compat.thinkingFormat: deepseek`（`off` 发送 `thinking: {type: disabled}`，其余等级额外发 `thinking: {type: enabled}`）；DeepSeek 自身路由模型自带 `off/low/high/max`，起始默认值由 `llm-deepseek.reasoningEffort` 控制
- **compat 开关规则**：写下的键必须给值（冒号留空被拒绝）；开关归属协议，某协议不接受的开关报错列出可用项；全部开关见生成的 `dsh-llm-pi-ai` 配置参考（config-catalog 的 `PiAiCompatProfile`）

```yaml
llm-pi-ai:
  providers:
    my-gateway:
      apiKeyEnv: GATEWAY_API_KEY
      api: openai-completions
      baseURL: https://gateway.example/v1
      reasoning: high
      compat:
        supportsDeveloperRole: false
        maxTokensField: max_tokens
      models:
        - id: my-model
        - id: vision-preview
          input: [text, image]
        - id: my-reasoner
          compat:
            thinkingFormat: deepseek
          reasoningEfforts:
            off:
            high: high
            max: max
```

> 同步脚本只更新 `llm-pi-ai.providers.{渠道}.models` 列表；`apiKeyEnv`/`api`/`baseURL`/`compat`/`reasoning` 等已有字段不动（缺失时空值补充除外）。上述 `input`/`reasoningEfforts`/`compat` 等模型级字段在 API 响应含对应数据时可一并写入，但须与文件原有格式一致。

### zcode → `~/.zcode/v2/provider_config.json`

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

**schema 要点（严格约束，写入时不可违反；源自解包 zcode 0.16.9 运行时 zod schema 与内置 `zcode-builtin.json`）：**

- **providerId**：内置渠道为 `builtin:xxx`；自定义渠道为 **baseURL 域名主体**（去掉子域名与顶级后缀；多段顶级后缀如 `com.cn` 取 3 段中的主体，如 `developer.amd.com.cn` → `amd`；`{env:VAR}` 占位符无法解析域名时保留渠道原名）。**同主体不同 TLD 消歧**：不同域名提取出相同主体时（如 `api.agnes-ai.cn` 与 `api.agnes-ai.com` 均为 `agnes-ai`），命名**确定性带顶级后缀**——`agnes-ai-cn` 与 `agnes-ai-com`（`.` → `-`），与处理顺序无关，保证幂等；**禁止**用 `-2`/`-3` 序号后缀消歧（顺序依赖，重跑可能互换导致重复创建）。单一渠道时维持简洁主体（`tokenrouter`）。同一 `provider_config.json` 内不可重复
- **渠道条目**：`{providerId, providerName, config}`，`config` 字段集合**固定**为 `group`（`standard-personal`）、`access: {type: "api-key", apiKey}`、`api: {type, baseUrl}`、`personalModelIds[]`、`modelOrder[]`——**不可添加任何额外字段**（无 enabled/source/kind/models），字段顺序为 `group → access → api → personalModelIds → modelOrder`
- **api.type 映射**：pi 的 `openai-completions` → `openai-chat-completions`；pi 的 `anthropic` → `anthropic-messages`
- **模型条目**：`{modelId, config: {enabled: true}, providerId}`——`config` **只有 `enabled: true`**，不写 properties/optionSpecs/displayName 等
- **新增渠道时**：`providerRules` 追加条目、`providerOrder` 追加 ID、每个模型追加一条 `providerModelRules`；`personalModelIds` 与 `modelOrder` 内容相同（模型 id 顺序一致）
- **只合并模型时**：向目标渠道的 `personalModelIds`/`modelOrder` 追加新模型 id（两处都加），并向 `providerModelRules` 追加对应条目；已有条目一律不动

**完整 schema 枚举值（zod 严格模式，超出枚举即校验失败；个人渠道用不到的枚举仅作识别参考，勿写入）：**

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

#### zcode 全量同步（以 pi 为基准：provider + models + apiKey）

用户要求"以 pi 的渠道/模型为基准更新 zcode"时，直接运行技能自带脚本（幂等可重复执行；只改目标字段；密钥不回显）：

```bash
python3 scripts/sync-pi-to-zcode.py
```

脚本位置：`scripts/sync-pi-to-zcode.py`（与本文档同目录，相对路径以技能目录为基准）。执行前按需修改脚本顶部 `PI_PATH`/`ZC_PATH`/`ALIAS` 三个变量。

**脚本行为：**
- 备份（`.bak-YYYYMMDD`）→ 匹配渠道（按 `providerName` 规范化+别名映射）→ 合并 models（`personalModelIds`/`modelOrder` 追加缺失 + `providerModelRules` 补 `{modelId, config:{enabled:true}, providerId}`，幂等）→ 更新 apiKey（env 解析，正则含数字）→ 写回（不转义中文）→ 断言校验（渠道/模型条目字段集合与现有条目完全一致，只允许 models 新增与 apiKey 变化）
- 无对应渠道时按 schema 自动创建（providerId = baseURL 域名主体，同主体不同 TLD 时带顶级后缀消歧如 `agnes-ai-cn`，禁用序号后缀；字段集合固定，无额外字段）
- 输出即报告摘要：渠道名 / env 名 / 长度 / 变化状态，不含密钥内容

**要点：**
- 渠道名匹配用规范化+显式别名（如 `cloudflare-workers-ai` → `CloudFlare AI`），不能直接字符串比较
- 明文 apiKey 绝不打印；多轮执行幂等，不会重复添加
- 长脚本用 heredoc/独立脚本文件传给 python3，**不要用 bash 双引号 `-c "..."`**（会吞掉 `\$`/`\"` 转义导致正则失效）

### qoder 的 `providers` 段 → `~/.qoder/settings.json`（国外版）与 `~/.qoder-cn/settings.json`（国内版）（同一软件的两个版本目录，结构相同；**按目录存在情况同步，都存在则都同步**；CLI 文档记载的模型配置项见下方「Qoder CLI 模型配置」）
`providers.{渠道key}.models` 是**数组**，元素为 `{model, displayName, contextWindow, maxOutputTokens, capabilities}`。渠道 key 为 `qoder-custom-{UUID}`，渠道级字段为 `displayName`/`baseUrl`/`apiKey`（明文，渠道顶层）/`type`/`protocol`/`authType`/`model`（当前选中模型）：
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
> qoder 的 `apiKey` 是**明文 key**（不是 `!echo` 环境变量形式），读取时直接取值，注意勿将密钥写入日志/输出。写入时**只更新 `models` 数组**，保留原 provider 的其它字段（displayName/baseUrl/apiKey/type/protocol/authType/model）不变；新增元素建议带 `model`（id 字段名）、`displayName`、`contextWindow`/`maxOutputTokens` 与 `capabilities` 结构，与文件原有格式一致（schema 见下方「provider 条目 schema 基准」）。
> **渠道独立（重要）**：每个 pi 渠道对应**独立的 provider**、**独立的密钥**、**独立的模型列表**：
> - **匹配顺序**：baseUrl 去尾斜杠强绑定（唯一）→ ALIAS 显式映射 → 规范化 displayName（仅未占用、且未被其他渠道 baseUrl 强绑定的 provider）
> - **自动创建**：无匹配的渠道自动新建 provider（key=`qoder-custom-{uuid4}`，结构与现有条目一致，含 baseUrl/apiKey/type/protocol/authType/model/models/displayName）
> - **模型归属**：模型去供应商前缀后的短 id 属于哪个渠道就归哪个渠道；同步后 provider 只保留归属渠道的目标模型 + 用户手动添加的不属于任何渠道的模型，其它渠道的模型迁出（由各自渠道的 provider 接管）
> - **独立密钥**：每个 provider 只写自己归属渠道的 apiKey（env 解析），互不覆盖；newapi 等中转渠道的模型（如 `sense/deepseek-latest-flash`）即使 id 前缀与其它渠道同名（`sense/deepseek-v4-flash`）也是独立模型，归中转渠道（newapi），密钥用中转渠道自己的
> - **无目标模型渠道跳过**：模型为空或全非目标族的渠道不创建 provider、不写密钥（如 openrouter/opencode/kilo/v2ex/agnes）
> - **displayName**：baseUrl 匹配/新建时更新为渠道显示名（纠正错误归属，如误设为 Sense 的 newapi provider 纠正为 NewAPI）；弱匹配（ALIAS/displayName）时已有值保留、空值补充

#### provider 条目 schema 基准（同步写入的约束模板）

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

#### 「Qoder」国外版与国内版是同一个软件，仅版本目录不同

- **qoder**（桌面版与 CLI 是同一软件的两种形态，国外版与国内版仅目录不同）：国外版配置 `~/.qoder/settings.json`，国内版配置 `~/.qoder-cn/settings.json`，**两份文件结构完全相同**，`providers` 段即其 BYOK 模型存储。**同步目标检测：哪个目录存在就同步哪个；两个都存在则两个都同步，不再区分 qoder/qoder-cn/qodercli/qoderclicn**
- `~/.qoder/settings.json` 中的 `model`/`modelConfigs` 顶层键是 CLI 文档记载的配置项，与 `providers` 段并存互不冲突

以下为 **Qoder** 的模型配置（`providers` 段为 BYOK 存储，以本 SKILL「provider 条目 schema 基准」为准）：

配置文件分层（用户级/项目级/本地级，合并生效）：
- **用户级（同步目标）**：`~/.qoder/settings.json`（国外版）与 `~/.qoder-cn/settings.json`（国内版）；**禁止写项目级** `<项目>/.qoder/settings.json` 与本地级 `settings.local.json`
- JSON Schema 位于项目 `schemas/settings.schema.json`，可用于编辑器补全

`model` / `modelConfigs`（模型相关顶层配置项）：

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

#### 多工具全量同步（pi 为基准：opencode / dsh / omp）

与 zcode 同步同模式，按工具选脚本（均在 `scripts/` 下，幂等可重复执行，自动备份+断言校验）：

| 脚本 | 目标配置 | models 格式 | apiKey 处理 |
|------|----------|-------------|-------------|
| `sync-pi-to-opencode.py` | `~/.config/opencode/opencode.json` | 对象 map（key=id，value 含 family=id 前缀或渠道名） | 保留 `{env:XXX}` 占位符 |
| `sync-pi-to-dsh.py` | `~/.dsh/settings.yaml` | 列表仅 `id` | 保留 `apiKeyEnv` 变量名 |
| `sync-pi-to-omp.py` | `~/.omp/agent/models.yml` | 列表 `{id, name}` | 保留 `!echo` 占位符（env 名可能不同，如 omp kilo 用 `NVIDIA_API_KEY` 而非 `KILO_API_KEY`，不可覆盖） |
| `sync-pi-to-qoder.py` | `~/.qoder/settings.json`（国外版）与 `~/.qoder-cn/settings.json`（国内版）（providers 段，按目录存在情况同步） | 数组（元素 id 字段名为 `model`，含 displayName/contextWindow/maxOutputTokens/capabilities） | **写死实值**（明文 apiKey，渠道顶层） |
| `sync-pi-to-codebuddy.py` | `~/.codebuddy/models.json` | 扁平 models 数组（每模型独立条目，含 id/name/vendor/url/apiKey/supports*） | **写死明文实值**（从 pi 的 `!echo -n "$VAR"` 解析环境变量后写实值，与 qoder 一致；现有 `${VAR}` 条目一并转换为明文） |

```bash
python3 scripts/sync-pi-to-opencode.py
python3 scripts/sync-pi-to-dsh.py
python3 scripts/sync-pi-to-omp.py
python3 scripts/sync-pi-to-qoder.py
python3 scripts/sync-pi-to-codebuddy.py
```

**上游免费渠道（kilo / openrouter）**：
- 这两个渠道同步到 **zcode / dsh / qoder** 时**不走 pi models 基准**，改由 `scripts/fetch_free.py` 从上游 `GET {baseUrl}/models` 提取**免费模型**，须同时满足：
  1. **免费**：id 含 `:free`/`-free`/`/free` 标签，或 `pricing.prompt`/`completion` 均为 0（含临时免费）
  2. **最近一年内更新**：`created` 时间戳在一年内；无时间数据的剔除（如 kilo 的 `kilo-auto/free` 聚合入口）
  3. **上下文**：`context_length`（顶层或 `top_provider` 内）若存在则必须 >100K；无 context 数据的保留（如 opencode 的 /models 无此字段）
  4. 剔除图像/视频/音频类（lyria/image/video 等）
- **opencode 渠道不同步**（SKIP_CHANNELS）：其上游价格数据不正确，无法可靠判定免费；各工具中已有的 opencode provider 已手动清除，后续同步脚本也会跳过该渠道
- 提取结果缓存 `~/.cache/model-channel-sync/free-{渠道}.json`（1 小时）；上游请求失败回退上次缓存，无缓存则回退 pi models 并在报告中注明
- 同步到 **opencode 工具**（`sync-pi-to-opencode.py`）与 **omp / pi** 时维持 pi 基准不变（omp 的 kilo 密钥 env 名可能不同，不可覆盖）
- qoder 归属判定豁免：这两个渠道的上游免费模型（含 short id）归对应渠道 provider 所有，不参与跨渠道迁出判定
- 注意：同步脚本为**合并式（只增不删）**，上游已下架或不再满足过滤条件的模型不会从目标配置自动移除；如需清理需手动处理

qoder 专属规则：
- 配置顶层同时含 `model`/`modelConfigs` 键与 `providers` 段（BYOK 模型存储，桌面版与 CLI 共用），渠道 key 为 `qoder-custom-{UUID}`（自动创建时生成 uuid4）；渠道字段：`displayName`/`baseUrl`（顶层、**小写 l**）/`apiKey`（**明文实值**，非占位符）/`type`/`protocol`/`authType`/`model`（当前选中模型）/`models`

**codebuddy 专属规则**（`sync-pi-to-codebuddy.py`，文档 https://www.codebuddy.cn/docs/cli/models）：

#### codebuddy `models.json` 配置结构

配置文件位置与优先级：
- **用户级**：`~/.codebuddy/models.json`（全局）
- **项目级**：`<workspace>/.codebuddy/models.json`（优先级高于用户级，同 `id` 模型覆盖用户级定义；`availableModels` 字段项目级完全覆盖、不合并）

**写入范围（重要）**：本技能只写**用户级** `~/.codebuddy/models.json`，**禁止修改项目级** `<workspace>/.codebuddy/models.json`——项目级配置优先级更高，会覆盖全局同名模型，且属于项目仓库文件，不应由同步写入。
- 合并策略 SmartMerge：同 `id` 覆盖、不同 `id` 追加；`availableModels` 过滤在所有合并完成后执行
- 支持**热重载**（变更自动检测，1 秒防抖），配置更新后自动同步，编辑后无需重启

顶层结构：
```json
{
  "models": [
    {
      "id": "model-id",
      "name": "Model Display Name",
      "vendor": "vendor-name",
      "apiKey": "${ENV_VAR_NAME}",
      "maxInputTokens": 200000,
      "maxOutputTokens": 8192,
      "url": "https://api.example.com/v1/chat/completions",
      "temperature": 0.7,
      "supportsToolCall": true,
      "supportsImages": true,
      "supportsReasoning": true,
      "relatedModels": {
        "lite": "model-id-lite",
        "reasoning": "model-id-reasoning"
      }
    }
  ],
  "availableModels": ["model-id-1", "model-id-2"]
}
```

`models` 数组元素（LanguageModel）字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✓ | 模型唯一标识符 |
| `name` | string | — | 模型显示名称 |
| `vendor` | string | — | 模型供应商（如 OpenAI, Google） |
| `apiKey` | string | — | API 密钥，支持环境变量引用 `${VAR_NAME}` |
| `maxInputTokens` | number | — | 最大输入 token 数 |
| `maxOutputTokens` | number | — | 最大输出 token 数 |
| `url` | string | — | API 端点，支持 `${VAR}` 引用，**必须是完整路径**（一般以 `/chat/completions` 结尾，如 `https://api.openai.com/v1/chat/completions`；只写 `https://api.openai.com/v1` 是错的） |
| `temperature` | number | — | 采样温度 0-2 |
| `supportsToolCall` | boolean | — | 是否支持工具调用 |
| `supportsImages` | boolean | — | 是否支持图片输入 |
| `supportsReasoning` | boolean | — | 是否支持推理模式 |
| `relatedModels` | object | — | 场景关联模型：`lite`/`reasoning` 已生效；`subagent`/`vision`/`longContext` 预留未启用 |

`availableModels`（`Array<string>`）：控制下拉列表显示哪些模型 id；未配置或为空则显示全部。通过 `models.json` 添加的模型自动带 `custom` 标签。

**环境变量引用（可选）**：`apiKey` 和 `url` 支持 `${VAR_NAME}` 语法，CLI 启动时解析；变量不存在则保留原始占位符（导致 API 调用失败）。建议文件权限 `600`，勿提交含明文密钥的文件到版本库——同步脚本不采用 `${VAR}` 而是写死明文实值（与 qoder 一致），因此该文件切勿提交到版本库。

**relatedModels 回退规则**：自定义模型**不继承**内置 `defaultRelatedModels`；主模型未声明 `relatedModels` 且无环境变量/`variantModels` 覆盖时，`lite`/`reasoning` 回退到主模型。场景变体解析优先级（高→低）：环境变量（`CODEBUDDY_SMALL_FAST_MODEL`=lite、`CODEBUDDY_BIG_SLOW_MODEL`=reasoning）→ 项目级 `variantModels[variant]`（存于 `settings.json`）→ 用户级 `variantModels[variant]` → 主模型条目 `relatedModels[variant]` → 内置 `defaultRelatedModels[variant]`（仅内置模型）→ 主模型自身。

- 结构与其它平台根本不同：**无渠道层级**，`models` 是扁平数组，每个模型是独立条目（`id`/`name`/`vendor`/`url`/`apiKey`/`supportsToolCall`/`supportsImages`/`supportsReasoning`/`useCustomProtocol`）
- **name 格式**：统一为 **`{vendor} - {模型名}`**（如 `Sense - DeepSeek V4 Flash`、`OpenRouter - Inkling Small (Free)`）；pi 模型 name 本身已带渠道前缀时先去掉该前缀再拼接，避免 `AMD - AMD DeepSeek...` 式重复（正则 `^{vendor}[\s\-]*` 忽略大小写匹配后剔除）
- **展开规则**：pi 每个渠道的每个模型 → 一条 codebuddy 条目；`vendor` = 渠道显示名；`url` = 渠道 baseUrl 规范化（去尾斜杠；若已以 `/chat/completions` 结尾则原样保留，否则拼接 `/chat/completions`，文档要求 url 必须含完整路径）
- **apiKey 明文实值**：从 pi 的 `!echo -n "$VAR"` 解析环境变量后**写死实值**（与 qoder 一致，不写 `${VAR}` 变量引用）；env 未设置则密钥空缺并在报告注明
- **现有条目 apiKey 规范化为明文**：`${VAR}` 变量引用条目按条目内变量名解析后转换为明文实值；已是明文的保留不动。其它字段（url/vendor/name/supports*）以 pi 为权威值；现有条目的额外字段（如 `maxInputTokens`/`maxOutputTokens`）保留
- **同模型多渠道去重**：codebuddy 扁平数组中 `id` 必须唯一；同模型在 pi 多渠道重复出现时按渠道优先级（sense/amd 最高，openrouter/kilo 最低）只保留一条
- **手工条目原样保留**（pi 中无对应的条目不删，只增不删）
- 能力字段：`supportsImages` = pi 模型 input 含 `image` 或 id 名含 vision/vl；`supportsReasoning` = pi 模型 `reasoning` 为 true；`supportsToolCall` 默认 true；`useCustomProtocol` 默认 false
- `models` 是**数组**，元素 id 字段名为 `model`（非 pi/dsh 的 `id`、非 zcode 的 `personalModelIds`），含 `displayName`/`contextWindow`/`maxOutputTokens`/`capabilities`
- **渠道独立**：每渠道独立 provider + 独立密钥 + 独立模型；baseUrl 强绑定匹配优先，无匹配自动创建，无模型渠道跳过；模型归属按短 id 匹配渠道，其它渠道模型迁出（各自渠道的 provider 接管）
- **展开**：每供应商的模型全部补入 models 数组；**模型筛选**：openrouter/opencode 渠道只补**免费模型**（id 含 `:free`/`-free`/`/free`），其它渠道**全量同步**；**模型 displayName 统一为 `{渠道显示名} - {模型名}` 格式**（如 `NewAPI - Sense DeepSeek Latest Flash`、`Sense - DeepSeek V4 Flash`；模型名已以渠道名开头则去重，如 amd 的 `AMD DeepSeek V4 Flash` → `AMD - DeepSeek V4 Flash`）
- **模型 id 保持 pi 原样**：不得擅自添加任何前缀（sense 渠道的 `deepseek-v4-flash` 就是 `deepseek-v4-flash`，不写 `sense/deepseek-v4-flash`；newapi 渠道的 `amd/deepseek-latest-flash` 本身带前缀则原样保留）；当前选中模型 `model` 字段同样用 pi 原样 id
- `apiKey`：**写死实值**（qoder 不支持 env 引用），每 provider 只写归属渠道的 env 值
- 顶层 `baseUrl`/`type`/`protocol`/`authType` 同步时**不动**；`model`（当前选中）用 pi 原样 id（允许去误加前缀规范化 + **版本族升级**，见下条）；`displayName` 在 baseUrl 匹配/新建时更新为渠道显示名，弱匹配时已有值保留（空值补充）
- **默认模型版本族规则（`model` 字段）**：同族（同一产品的不同版本号）模型存在更高版本时，`model` 自动取**同族最高版本**——如渠道 models 含 `agnes-2.0-flash`/`agnes-2.5-flash`/`agnes-3.0-flash` 而 `model` 为 `agnes-2.5-flash` 时，应升级为 `agnes-3.0-flash`。族键提取：模型 id 取**最后一个 `/` 后的段**（无 `/` 取全段）小写后提取**开头连续字母**（`^[a-z]+`，提取不到用整段，如 `agnes-2.5-flash` → `agnes`、`qwen3.8-27b` → `qwen`）；版本号 = 该段**首个数字串**（`2.5` → `(2,5)`，无数字 → 空元组视为最低）。同版本或均无版本号一律不动（幂等）；`model` 为空时取首个模型同族的最高版本

共同要点：
- opencode/dsh/omp 三工具的 apiKey 均为环境变量引用（非明文），同步时保留目标现有引用，只合并 models（保留现有 + 补 pi 缺失）；**qoder 与 codebuddy 的 apiKey 均为写死明文字面值**（不保留 pi 的 `!echo` 占位符、也不写 `${VAR}` 变量引用），且都从 pi 的 `!echo -n "$VAR"` 解析环境变量后写实值；codebuddy 现有 `${VAR}` 条目同步时一并转换为明文
- **AMD 渠道全量同步**：AMD 渠道不区分免费/付费，同步时全量写入所有模型（不从上游筛选免费模型）
- **Sense 渠道版本族精简**：Sense 渠道只保留每个系列的最新版模型，例如 `sensenova-6.7-flash-lite` 和 `sensenova-6.8-flash-lite` 只保留 `sensenova-6.8-flash-lite`；`sensenova-u1-fast` 和 `sensenova-u1.5-fast` 只保留 `sensenova-u1.5-fast`。判断规则：同系列模型（id 含相同前缀如 `sensenova-*`）按版本号排序，只保留最高版本
- **baseURL / kind（兼容模式，opencode 为 npm、dsh/omp 为 api、qoder 为 type/protocol/authType/baseUrl）：不更新已有值**，仅当目标缺失/为空时补入——opencode 补 `{env:XXX_BASE_URL}` 占位符（由 apiKey 占位符推导）；dsh/omp 补 pi 的 baseURL 与 api；qoder 顶层字段（baseUrl/type/protocol/authType/displayName/model）一律不动，只合并 models 数组与更新 apiKey；**zcode（新版）无独立 baseURL/kind 字段**——`api.baseUrl`/`api.type` 已含于渠道条目，已有值不动、缺失时（新建渠道）由 pi 补入
- 匹配渠道：同名优先，规范化兜底（如 `cloudflare-workers-ai`）；opencode 无 v2ex 时正确跳过
- 写回：JSON 用 `json.dump(indent=2, ensure_ascii=False)`，YAML 用 `yaml.safe_dump(sort_keys=False, allow_unicode=True, default_flow_style=False)`；校验断言只允许 models 新增、apiKey 更新与 baseURL/kind 空值补充

### 其他工具
让用户提供配置文件路径与结构，遵循该工具现有格式。

**写入后必须校验**：JSON 用 `python3 -m json.tool`，YAML 用 `python3 -c "import yaml;yaml.safe_load(open(...))"`。

> **是否写入、写入哪些工具由用户决定，不要擅自修改任何配置文件。**

## pi 模型配置参考

pi 的模型配置文件位于 `~/.pi/agent/models.json`，结构为 `providers.{渠道}.models` 数组。完整文档见 [pi.dev/docs/latest/models](https://pi.dev/docs/latest/models)（源文件：pi 仓库 `packages/coding-agent/docs/models.md`）。

**写入范围（重要）**：本技能只写**用户级（全局）** `~/.pi/agent/models.json`，**禁止修改项目级**模型配置（如 `<workspace>/.pi/agent/models.json` 等项目内路径）——所有同步目标工具同理，一律只写用户级全局配置，不写项目仓库内的任何配置文件。

### 支持的 API 类型（`api` 字段）

| 值 | 说明 |
|----|------|
| `openai-completions` | OpenAI Chat Completions（最通用，默认常用） |
| `openai-responses` | OpenAI Responses API |
| `anthropic-messages` | Anthropic Messages API |
| `google-generative-ai` | Google Generative AI（自定义模型时 `baseUrl` 必填，如 `https://generativelanguage.googleapis.com/v1beta`） |

`api` 可设在 provider 级（对该渠道所有模型生效）或 model 级（覆盖单个模型）。

### Provider 字段

| 字段 | 说明 |
|------|------|
| `baseUrl` | API 端点 URL |
| `api` | API 类型（见上表） |
| `apiKey` | 可选；auth 也可由 `/login`/`auth.json` 或 CLI `--api-key` 提供，此时省略。未配置 auth 时模型仍加载但在 `/model` 中不可用 |
| `oauth` | 动态 OAuth 供应商类型（当前支持 `"radius"`，需网关 `baseUrl`） |
| `headers` | 自定义请求头（支持值解析，见下） |
| `authHeader` | 设 `true` 自动添加 `Authorization: Bearer <apiKey>` |
| `models` | 模型配置数组 |
| `modelOverrides` | 对内置/扩展注册模型的逐模型覆盖（见下） |
| `compat` | provider 级兼容性覆盖，对该渠道所有模型生效 |

### 值解析（Value Resolution，`apiKey` 与 `headers` 通用）

- **Shell 命令**：值以 `!command` 开头时执行整个命令并取 stdout，如 `"!security find-generic-password -ws 'anthropic'"`、`"!echo -n \"$ENV_VAR\""`；`models.json` 中命令在**请求时**解析，pi 不做 TTL/失败重用
- **环境变量插值**：`"$ENV_VAR"` 或 `"${ENV_VAR}"`，可嵌在更大字面量中（`"${KEY_PREFIX}_${KEY_SUFFIX}"`）；`$FOO_BAR` 取变量 `FOO_BAR`，`BAR` 是字面文本时用 `${FOO}_BAR`；变量不存在则值未解析
- **转义**：`"$$"` 输出字面 `$`；`"$!"` 输出字面 `!`（不触发命令执行）
- **字面量**：直接使用（`"sk-..."`）；纯大写字符串如 `MY_API_KEY` 是字面量，环境变量须带 `$` 前缀
- `/model` 的可用性检查只看已配置的 auth，**不执行** shell 命令

### Model 字段

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | 是 | — | 模型标识符，传递给 API |
| `name` | 否 | `id` | 可读标签，用于匹配（`--model` 模式）与次级详情文本；页脚/状态栏仍显示 `id` |
| `api` | 否 | 继承 provider 的 `api` | 覆盖 provider 的 API 类型 |
| `reasoning` | 否 | `false` | 是否支持扩展思考 |
| `thinkingLevelMap` | 否 | 省略 | 映射 pi 思考级别（`off`/`minimal`/`low`/`medium`/`high`/`xhigh`/`max`）到 provider 值；值为 string（发送该值）、`null`（该级别不支持，UI 隐藏）或省略（默认映射）；允许空洞 |
| `input` | 否 | `["text"]` | 输入类型：`["text"]` 或 `["text", "image"]` |
| `contextWindow` | 否 | `128000` | 上下文窗口大小（token） |
| `maxTokens` | 否 | `16384` | 最大输出 token 数 |
| `samplingParams` | 否 | 省略 | 自由对象，逐字段合并进每个请求体（键优先于 pi 自设字段）；仅 OpenAI 兼容 API（`openai-completions`/`openai-responses`/`azure-openai-responses`）生效，其它 API 忽略 |
| `cost` | 否 | 全零 | 每百万 token 计费 `{input, output, cacheRead, cacheWrite}`，可含 `tiers`（`inputTokensAbove` 阈值费率，多档命中取最高阈值） |
| `compat` | 否 | 继承 provider 的 `compat` | 兼容性覆盖，与 provider 级合并（模型级优先） |

`cost.tiers` 示例：
```json
{
  "cost": {
    "input": 5, "output": 30, "cacheRead": 0.5, "cacheWrite": 6.25,
    "tiers": [{ "inputTokensAbove": 272000, "input": 10, "output": 45, "cacheRead": 1, "cacheWrite": 12.5 }]
  }
}
```

### Full Example

```json
{
  "providers": {
    "ollama": {
      "baseUrl": "http://localhost:11434/v1",
      "api": "openai-completions",
      "apiKey": "ollama",
      "models": [
        {
          "id": "llama3.1:8b",
          "name": "Llama 3.1 8B (Local)",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 128000,
          "maxTokens": 32000,
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 }
        }
      ]
    }
  }
}
```

### 覆盖内置 provider 与 modelOverrides

- **只改端点**：内置 provider（如 `anthropic`）可只写 `baseUrl` 走代理，内置模型全部保留，已有 OAuth/API key 继续生效
- **合并自定义模型**：内置 provider 带 `models` 数组时，自定义模型按 `id` upsert——同 `id` 替换内置条目，新 `id` 追加，内置模型保留
- **modelOverrides**：不替换整个 models 列表，逐模型覆盖内置/扩展注册模型；支持字段：`name`、`reasoning`、`thinkingLevelMap`、`input`、`cost`（可部分）、`contextWindow`、`maxTokens`、`samplingParams`（逐键合并）、`headers`、`compat`；未知 id 忽略；与 `models` 同时存在时自定义模型合并在覆盖之后（同 `id` 自定义条目胜出）
```json
{
  "providers": {
    "openrouter": {
      "modelOverrides": {
        "anthropic/claude-sonnet-4": {
          "name": "Claude Sonnet 4 (Bedrock Route)",
          "compat": { "openRouterRouting": { "only": ["amazon-bedrock"] } }
        }
      }
    }
  }
}
```

### compat 常用字段（按 API 类型）

**OpenAI 兼容（openai-completions / openai-responses）**：`supportsStore`、`supportsDeveloperRole`（`developer` vs `system` 角色，本地服务常设 `false`）、`supportsReasoningEffort`、`supportsUsageInStreaming`、`supportsFinishReason`、`maxTokensField`（`max_completion_tokens` 或 `max_tokens`）、`requiresToolResultName`、`requiresAssistantAfterToolResult`、`requiresThinkingAsText`、`requiresReasoningContentOnAssistantMessages`、`thinkingFormat`（`reasoning_effort`/`openrouter`/`deepseek`/`together`/`baseten`/`zai`/`qwen`/`chat-template`/`qwen-chat-template`）、`chatTemplateKwargs`/`chatTemplateArgs`、`thinkingTokenBudgetField`（`thinking_token_budget`=vLLM、`thinking_budget`=Qwen/DashScope/SGLang、`thinking_budget_tokens`=llama.cpp）、`cacheControlFormat: "anthropic"`、`supportsStrictMode`、`supportsOpenAIGrammarTools`、`supportsLongCacheRetention`、`openRouterRouting`（原样发送到 OpenRouter 请求的 `provider` 字段）、`vercelGatewayRouting`（`only`/`order`）

**Anthropic Messages（anthropic-messages）**：`supportsEagerToolInputStreaming`（默认 `true`，代理拒绝时设 `false`）、`supportsLongCacheRetention`、`supportsCacheControlOnTools`、`forceAdaptiveThinking`（自适应思考 `thinking.type: "adaptive"`）、`supportsMidConvoEffort`、`allowEmptySignature`（仅对回放空签名 thinking 块的供应商设 `true`，真 Anthropic 拒绝空签名）、`supportsStrictTools`、`allowedFallbackModels`（最多 3 个服务端回退模型，需完整 `cost` 元数据；空数组禁用回退）

```json
{
  "providers": {
    "local-llm": {
      "baseUrl": "http://localhost:8080/v1",
      "api": "openai-completions",
      "compat": { "supportsDeveloperRole": false, "supportsReasoningEffort": false },
      "models": [{ "id": "gpt-oss:20b", "reasoning": true }]
    }
  }
}
```

### 写入 pi 时的字段映射

从 API 抓取模型信息写入 pi 的 `models.json` 时，字段映射如下：

| API 响应字段 | pi `models.json` 字段 | 说明 |
|-------------|----------------------|------|
| `id` | `id` | 模型标识符 |
| `name` | `name` | 可读标签 |
| `max_tokens` / `maxTokens` | `maxTokens` | 最大输出 token 数 |
| `context_length` / `contextWindow` | `contextWindow` | 上下文窗口大小 |
| `reasoning` | `reasoning` | 是否支持推理 |
| `input` | `input` | 输入类型 |
| `cost` | `cost` | 计费信息 |

写入时以 pi 现有配置结构为准，仅合并/新增模型条目，保留已有条目不变。文件每次打开 `/model` 时自动重载，编辑后无需重启。

## omp (Oh My Pi) 模型配置参考

omp 的模型配置文件位于 `~/.omp/agent/models.yml`（`.yaml` 为次选；仅存在旧 `models.json` 时自动迁移为 `models.yml`），结构为 `providers.{渠道}.models` YAML 列表。根对象**只接受 `providers`**。完整文档见 [omp.sh/docs/custom-models](https://omp.sh/docs/custom-models)。

本地推理服务免配置：omp 自动发现 Ollama（`http://127.0.0.1:11434`）、llama.cpp（`http://127.0.0.1:8080`）、LM Studio（`http://127.0.0.1:1234/v1`）。

### omp Provider 字段

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

### omp 的 `api` 值

`openai-completions`（Chat Completions）、`openai-responses`（Responses API）、`openai-codex-responses`（Codex 风味）、`azure-openai-responses`、`anthropic-messages`、`bedrock-converse-stream`、`google-generative-ai`、`google-gemini-cli`、`google-vertex`。其它 wire 协议需扩展，不能靠加字符串。

### omp 的 `apiKey` 解析规则（与 pi 不同）

1. 值以 `!` 开头 → 执行 shell 命令，取 stdout（trim 后）作为密钥
2. 否则查找**同名环境变量**（直接写变量名，**不带 `$`**，如 `apiKey: MYCO_LLM_API_KEY`）
3. 环境变量不存在 → 用配置文本作为**字面量**密钥

`headers` 值用同样规则。这与 pi 的 `!echo -n "$VAR"` / `"$VAR"` 形式不同，同步时须按目标格式转换。

### omp Model 字段

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

### omp 的 `thinking` 字段

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

### omp 的 `discovery`（免维护 models 列表）

`discovery: { type: ..., timeoutMs: ... }`，type 取值：`ollama`（Ollama 原生端点）、`llama.cpp`、`lm-studio`、`openai-models-list`（通用 `GET /v1/models`）、`litellm`（富元数据路由，回退 `/v1/models`）、`proxy`（OpenAI/Anthropic 混合代理，按 `supported_endpoint_types` 推导模型 API）。除 `proxy` 外都要求 provider 级 `api`。验证/刷新：`omp models <provider>`、`omp models refresh <provider>`。

### omp 的覆盖机制

- 不带 `models` 的 provider 条目是**修改内置 provider**（如给 `openai` 换 `baseUrl`/`apiKey`/`headers`），不替换其目录
- `modelOverrides` 逐模型补丁（`gpt-5.4: {contextWindow: 400000}`）
- 自定义 `models` 条目与现有模型同 provider 同 `id` 时，替换该模型的传输配置
- 验证失败提示 `models.yml validation failed` + 出错字段；实测：`omp -p --model <provider>/<model-id> "Reply with only OK"`

### omp 最小与完整示例

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

### 写入 omp 时的要点（汇总）

- 只写全局 `~/.omp/agent/models.yml`，禁止项目级
- `models` 是 YAML 列表，元素 `{id, name}` 起步，有数据时补 `reasoning`/`input`/`contextWindow`/`maxTokens`/`cost`
- `apiKey` 用 env 变量名裸形式（omp 的解析规则），同步保留 omp 现有引用（env 名可能不同，如 omp kilo 用 `NVIDIA_API_KEY`，不可覆盖）
- `baseURL`/`api` 等渠道字段：已有值不动，缺失/为空才从 pi 补入
- 写回后用 `python3 -c "import yaml;yaml.safe_load(open(...))"` 校验

## 注意事项

- **开工前必须确认渠道、筛选方式和目标工具**，不要擅自假设。
- **所有工具（pi/omp/opencode/dsh/zcode/qoder/codebuddy）一律只写用户级全局配置**，禁止修改项目级/工作区内的模型配置文件。
- 不要只依赖 `free` 标签，若渠道提供定价字段，用价格=0 判断更完整。
- 渠道若没有定价字段，要退化到 `free-tag`/`keyword` 并明确告知用户。
- 不要跳过连通性测试，很多"免费"模型实际不可用。
- 报告给用户的免费清单必须是**实测可用**的，不可用的一律列入剔除原因。
- 写入多工具配置时，务必匹配各工具（pi/omp/opencode/dsh/zcode/qoder）不同的结构格式，并校验。
- dsh 的 models 元素只含 `id`，且路径是 `llm-pi-ai.providers.{渠道}`，不要与 pi 的 `providers.{渠道}` 混淆。
- zcode（`provider_config.json`）为规则式结构：渠道在 `config.providerConfigRules.providerRules[]`（`{providerId, providerName, config}`，config 字段固定为 group/access/api/personalModelIds/modelOrder，**不可加额外字段**），模型在 `config.modelConfigRules.providerModelRules[]`（`{modelId, config:{enabled:true}, providerId}`）；自定义渠道 `providerId` 为 baseURL 域名主体（如 `tokenrouter`；同主体不同 TLD 时带顶级后缀消歧如 `agnes-ai-cn`，禁用序号后缀），内置为 `builtin:xxx`；`access.apiKey` 为明文（仅此一种形式，无 env 引用）；`api.type: anthropic-messages` 的渠道无 `/models` 端点，模型列表从 `personalModelIds` 读取。
- qoder 的渠道 key 是 `qoder-custom-{UUID}`，`apiKey` 为明文且位于渠道顶层（非 zcode 的 `access` 内），`models` 是数组、id 字段名为 `model`，`baseUrl` 是顶层小写 l 形式——与 zcode 的 `access.apiKey`/`api.baseUrl`/`personalModelIds`、dsh 的 `baseURL` 全大写均不同；每渠道独立 provider + 独立密钥 + 独立模型（模型归属按短 id 匹配渠道，其它渠道模型迁出），`baseUrl`/`type`/`protocol`/`authType` 不动；`model`（当前选中）随同步做**版本族升级**：id 末段（`/` 后）开头连续字母为族键、首个数字串为版本号，同族存在更高版本时自动改用最新版（`agnes-2.5-flash` → `agnes-3.0-flash`）。**Qoder 是同一软件的国外版（`~/.qoder`）与国内版（`~/.qoder-cn`），结构相同；按目录存在情况同步，都存在则都同步，不再区分 qoder/qoder-cn/qodercli/qoderclicn**。
- 模型筛选与显示：openrouter/opencode 渠道只补**免费模型**（id 含 `:free`/`-free`/`/free`），其它渠道全量同步；Sense 渠道需执行**版本族精简**（只保留每个系列的最新版，如 sensenova-6.8-flash-lite 保留、sensenova-6.7-flash-lite 剔除）；kilo/openrouter 渠道同步到 zcode/dsh/qoder 时改从**上游提取免费模型**（`scripts/fetch_free.py`，须同时满足：free 标签或价格为 0、**最近一年内更新**、**context 存在时 >100K**，剔除图像/视频类）；**opencode 渠道不同步**（上游价格数据不正确）；模型 displayName/name 统一为 **`{渠道显示名} - {模型名}`** 格式（如 `NewAPI - Sense DeepSeek Latest Flash`、`Sense - DeepSeek V4 Flash`，模型名已含渠道名则去重）。
- 同步/写入前先做幂等核对（缺失比对），0 缺失时无写入，避免无意义重写文件。
- 环境变量名正则须含数字（`[A-Z0-9_]+`）；bash 传参用 heredoc 避免 `\$`/`\"` 转义被吞；写回前备份、写回后对比备份断言只动了目标字段。
- 写入明文密钥后报告**绝不回显密钥内容**，只报告长度/变化状态。
- 涉及写入配置时先让用户决定，不要擅自修改。