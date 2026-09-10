---
name: model-channel-sync
description: >-
  管理 AI 模型渠道（provider）配置：①提取真正可用的免费/零价模型；②以 pi 等平台配置为基准，同步/更新渠道、模型、APIKEY 到多个 agent 工具（zcode、dsh、pi、omp、opencode、qoder-cn 等）的配置文件。
  凡是用户提到"获取/提取/列出/查看 XX 渠道免费模型"、"从价格判断免费模型"、"查价格为零的模型"、"有哪些免费模型可用"、
  "给 XX 渠道加免费模型"、"这个免费模型能用吗/测试一下"、"把模型更新到 pi/omp/opencode/dsh"、
  "以 pi 为基准更新 XX 渠道"、"同步渠道/模型/APIKEY 到 XX"、"更新 XX 的 APIKEY"时，都应使用此技能。
  技能通用性强：支持配置文件中所有 OpenAI 兼容渠道（openrouter、kilo、opencode、newapi、nvidia、atomgit 等）。
  提取场景需用户指定：①目标渠道，②筛选方式（按价格=0 / free 标签 / 关键词等），流程为抓取 → 筛选 → 连通性实测 → 剔除不可用 → 给出结论；同步场景需指定源与目标工具，流程为匹配渠道 → 合并模型 → 更新密钥 → 写回校验。
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
- **zcode（ZCode）**：`~/.zcode/v2/config.json`
- **qoder-cn（Qoder-CN）**：`~/.qoder-cn/settings.json`
- 其他工具：让用户提供配置文件路径与结构

> 默认查询/提取只需渠道+筛选方式，写入配置时才确认目标工具。
> 注意：dsh 的渠道配置并不来自 pi 的 `models.json`，其结构与 pi 不同（见「第 1 步」和「dsh」章节），读取 baseUrl/apiKeyEnv 时应以 `~/.dsh/settings.yaml` 为准；zcode 同理，见「第 1 步」和「zcode」章节。

## 依赖

- 目标渠道的 `baseUrl` 与 `apiKey`（通常从 pi 配置文件读取；若写入目标是 dsh，则从 `~/.dsh/settings.yaml` 读取）
- `curl` 和 `python3`

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

**zcode 配置**：若目标是 zcode，则从 `~/.zcode/v2/config.json` 读取，结构为 `provider.{渠道}`，渠道 key 为 UUID（自定义渠道）或 `builtin:xxx`（内置渠道）。字段为 `name`、`kind`（`openai-compatible`/`anthropic`）、`options.apiKey`（**明文 key**，非 `!echo` 环境变量形式）、`options.baseURL`、`enabled`、`source`、`models`：

```bash
# 示例：zcode 的 OpenRouter（渠道 key 为 UUID）
python3 -c "
import json
c = json.load(open('$HOME/.zcode/v2/config.json'))
p = c['provider']['57441beb-ec54-4130-a936-589d9ea151ee']  # 渠道 key
print('BASE_URL:', p['options']['baseURL'])
print('API_KEY:', p['options']['apiKey'])
print('KIND:', p['kind'])
"
```
> 注意：zcode 的 `kind` 为 `anthropic` 的渠道通常不支持 `GET {baseURL}/models`（Anthropic 协议无此端点），此时直接从该渠道 `models` map 的 key 读取模型列表，并告知用户改用配置读取方式。

**渠道匹配方法（pi → zcode）**：zcode 的渠道 key 是 UUID/`builtin:xxx`，与 pi 的渠道名不同，需按 `name` 字段匹配。匹配前先规范化（小写并去除非字母数字）再比较；规范化后仍不一致的用显式别名（如 pi 的 `cloudflare-workers-ai` 规范化后是 `cloudflareworkersai`，zcode 的 `CloudFlare AI` 规范化后是 `cloudflareai`，需手动映射）。pi 的 `apiKey` 形如 `!echo -n "$ENV_VAR"`，提取环境变量名时正则须含数字：`r'!echo -n "\$([A-Z0-9_]+)"'`（变量名可能是 `DS2API_API_KEY`、`V2EX_API_KEY` 这类含数字的形式）。

**qoder-cn 配置**：若目标是 qoder-cn，则从 `~/.qoder-cn/settings.json` 读取，结构为 `providers.{渠道key}`，渠道 key 为 `qoder-custom-{UUID}`。字段为 `displayName`、`baseUrl`（渠道顶层、**小写 l**，非 zcode 的 `options.baseURL`）、`apiKey`（**明文 key**）、`type`/`protocol`/`authType`、`model`（当前选中模型）、`models`（**数组**，元素含 `model`/`displayName`/`contextWindow`/`maxOutputTokens`/`capabilities`）：

```bash
# 示例：qoder-cn
python3 -c "
import json
c = json.load(open('$HOME/.qoder-cn/settings.json'))
for k, p in c['providers'].items():
    print('KEY:', k)
    print('BASE_URL:', p['baseUrl'])
    print('TYPE:', p['type'])
    print('MODELS:', [m['model'] for m in p.get('models', [])])
"
```
> 注意：qoder-cn 的 `apiKey` 为明文且位于渠道顶层（非 zcode 的 `options` 内）；`models` 是数组、id 字段名为 `model`（非 pi/dsh 的 `id`、非 zcode 的 map key），`baseUrl` 顶层小写 l（非 dsh 的 `baseURL` 全大写）。

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
`providers.{渠道}.models` 是**数组**，元素为 `{id, name}`：
```json
{ "id": "stealth/ox-alpha", "name": "Stealth OX Alpha (Free)" }
```

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

### zcode → `~/.zcode/v2/config.json`
`provider.{渠道}.models` 是**对象（map）**，key 为模型 id，value 为对象（可含 `name`、`limit.context`、`reasoning`、`zcode.modified/priority` 等）。渠道 key 为 UUID（自定义渠道）或 `builtin:xxx`（内置渠道），渠道级字段为 `name`/`kind`/`options.apiKey`/`options.baseURL`/`enabled`/`source`：
```json
"provider": {
  "{渠道key}": {
    "name": "OpenRouter",
    "kind": "openai-compatible",
    "options": {
      "apiKey": "sk-or-v1-xxx",
      "baseURL": "https://openrouter.ai/api/v1",
      "apiKeyRequired": true
    },
    "enabled": false,
    "source": "custom",
    "models": {
      "nvidia/nemotron-3-ultra-550b-a55b:free": {
        "name": "NVIDIA Nemotron Ultra 550B (Free)",
        "limit": { "context": 200000 },
        "zcode": { "modified": true, "priority": 99 }
      }
    }
  }
}
```
> zcode 的 `options.apiKey` 是**明文 key**（不是 `!echo` 环境变量形式），读取时直接取值，注意勿将密钥写入日志/输出。写入时**只更新 `models` map**，保留原 provider 的其它字段（name/kind/options/enabled/source）不变；新增模型条目建议带 `name`、`limit.context`（参考同渠道其它条目，如 200000）与 `zcode: {modified: true, priority: N}`（N 取现有条目 max+1），与文件原有格式一致。

#### zcode 全量同步（以 pi 为基准：provider + models + apiKey）

用户要求"以 pi 的渠道/模型为基准更新 zcode"时，直接运行技能自带脚本（幂等可重复执行；只改目标字段；密钥不回显）：

```bash
python3 scripts/sync-pi-to-zcode.py
```

脚本位置：`scripts/sync-pi-to-zcode.py`（与本文档同目录，相对路径以技能目录为基准）。执行前按需修改脚本顶部 `PI_PATH`/`ZC_PATH`/`ALIAS` 三个变量。

**脚本行为：**
- 备份（`.bak-YYYYMMDD`）→ 匹配渠道（规范化+别名映射）→ 合并 models（保留 zcode 现有 + 补 pi 缺失，幂等）→ 更新 apiKey（env 解析，正则含数字）→ 写回（保键序/不转义中文）→ 断言校验（只允许 models 新增与 apiKey 变化）
- **baseURL / kind（兼容模式）：不更新已有值**，仅当目标缺失/为空时从 pi 补入（kind 由 pi 的 `api` 字段映射：`openai-completions` → `openai-compatible`，`anthropic` → `anthropic`）
- 输出即报告摘要：渠道名 / env 名 / 长度 / 变化状态，不含密钥内容

**要点：**
- 渠道名匹配用规范化+显式别名（如 `cloudflare-workers-ai` → `CloudFlare AI`），不能直接字符串比较
- 明文 apiKey 绝不打印；多轮执行幂等，不会重复添加
- 长脚本用 heredoc/独立脚本文件传给 python3，**不要用 bash 双引号 `-c "..."`**（会吞掉 `\$`/`\"` 转义导致正则失效）

### qoder-cn → `~/.qoder-cn/settings.json`
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
> qoder-cn 的 `apiKey` 是**明文 key**（不是 `!echo` 环境变量形式），读取时直接取值，注意勿将密钥写入日志/输出。写入时**只更新 `models` 数组**，保留原 provider 的其它字段（displayName/baseUrl/apiKey/type/protocol/authType/model）不变；新增元素建议带 `model`（id 字段名）、`displayName`、`contextWindow`/`maxOutputTokens`（参考同渠道现有元素，如 200000/8192）与 `capabilities` 结构，与文件原有格式一致。
> **渠道独立（重要）**：每个 pi 渠道对应**独立的 provider**、**独立的密钥**、**独立的模型列表**：
> - **匹配顺序**：baseUrl 去尾斜杠强绑定（唯一）→ ALIAS 显式映射 → 规范化 displayName（仅未占用、且未被其他渠道 baseUrl 强绑定的 provider）
> - **自动创建**：无匹配的渠道自动新建 provider（key=`qoder-custom-{uuid4}`，结构与现有条目一致，含 baseUrl/apiKey/type/protocol/authType/model/models/displayName）
> - **模型归属**：模型去供应商前缀后的短 id 属于哪个渠道就归哪个渠道；同步后 provider 只保留归属渠道的目标模型 + 用户手动添加的不属于任何渠道的模型，其它渠道的模型迁出（由各自渠道的 provider 接管）
> - **独立密钥**：每个 provider 只写自己归属渠道的 apiKey（env 解析），互不覆盖；newapi 等中转渠道的模型（如 `sense/deepseek-latest-flash`）即使 id 前缀与其它渠道同名（`sense/deepseek-v4-flash`）也是独立模型，归中转渠道（newapi），密钥用中转渠道自己的
> - **无目标模型渠道跳过**：模型为空或全非目标族的渠道不创建 provider、不写密钥（如 openrouter/opencode/kilo/v2ex/agnes）
> - **displayName**：baseUrl 匹配/新建时更新为渠道显示名（纠正错误归属，如误设为 Sense 的 newapi provider 纠正为 NewAPI）；弱匹配（ALIAS/displayName）时已有值保留、空值补充

#### 多工具全量同步（pi 为基准：opencode / dsh / omp）

与 zcode 同步同模式，按工具选脚本（均在 `scripts/` 下，幂等可重复执行，自动备份+断言校验）：

| 脚本 | 目标配置 | models 格式 | apiKey 处理 |
|------|----------|-------------|-------------|
| `sync-pi-to-opencode.py` | `~/.config/opencode/opencode.json` | 对象 map（key=id，value 含 family=id 前缀或渠道名） | 保留 `{env:XXX}` 占位符 |
| `sync-pi-to-dsh.py` | `~/.dsh/settings.yaml` | 列表仅 `id` | 保留 `apiKeyEnv` 变量名 |
| `sync-pi-to-omp.py` | `~/.omp/agent/models.yml` | 列表 `{id, name}` | 保留 `!echo` 占位符（env 名可能不同，如 omp kilo 用 `NVIDIA_API_KEY` 而非 `KILO_API_KEY`，不可覆盖） |
| `sync-pi-to-qoder-cn.py` | `~/.qoder-cn/settings.json` | 数组（元素 id 字段名为 `model`，含 displayName/contextWindow/maxOutputTokens/capabilities） | **写死实值**（明文 apiKey，渠道顶层） |

```bash
python3 scripts/sync-pi-to-opencode.py
python3 scripts/sync-pi-to-dsh.py
python3 scripts/sync-pi-to-omp.py
python3 scripts/sync-pi-to-qoder-cn.py
```

**上游免费渠道（kilo / openrouter）**：
- 这两个渠道同步到 **zcode / dsh / qoder-cn** 时**不走 pi models 基准**，改由 `scripts/fetch_free.py` 从上游 `GET {baseUrl}/models` 提取**免费模型**，须同时满足：
  1. **免费**：id 含 `:free`/`-free`/`/free` 标签，或 `pricing.prompt`/`completion` 均为 0（含临时免费）
  2. **最近一年内更新**：`created` 时间戳在一年内；无时间数据的剔除（如 kilo 的 `kilo-auto/free` 聚合入口）
  3. **上下文**：`context_length`（顶层或 `top_provider` 内）若存在则必须 >100K；无 context 数据的保留（如 opencode 的 /models 无此字段）
  4. 剔除图像/视频/音频类（lyria/image/video 等）
- **opencode 渠道不同步**（SKIP_CHANNELS）：其上游价格数据不正确，无法可靠判定免费；各工具中已有的 opencode provider 已手动清除，后续同步脚本也会跳过该渠道
- 提取结果缓存 `~/.cache/model-channel-sync/free-{渠道}.json`（1 小时）；上游请求失败回退上次缓存，无缓存则回退 pi models 并在报告中注明
- 同步到 **opencode 工具**（`sync-pi-to-opencode.py`）与 **omp / pi** 时维持 pi 基准不变（omp 的 kilo 密钥 env 名可能不同，不可覆盖）
- qoder-cn 归属判定豁免：这两个渠道的上游免费模型（含 short id）归对应渠道 provider 所有，不参与跨渠道迁出判定
- 注意：同步脚本为**合并式（只增不删）**，上游已下架或不再满足过滤条件的模型不会从目标配置自动移除；如需清理需手动处理

**qoder-cn 专属规则**：
- 配置顶层为 `providers`，渠道 key 为 `qoder-custom-{UUID}`（自动创建时生成 uuid4）；渠道字段：`displayName`/`baseUrl`（顶层、**小写 l**）/`apiKey`（**明文实值**，非占位符）/`type`/`protocol`/`authType`/`model`（当前选中模型）/`models`
- `models` 是**数组**，元素 id 字段名为 `model`（非 pi/dsh 的 `id`、非 zcode 的 map key），含 `displayName`/`contextWindow`/`maxOutputTokens`/`capabilities`
- **渠道独立**：每渠道独立 provider + 独立密钥 + 独立模型；baseUrl 强绑定匹配优先，无匹配自动创建，无模型渠道跳过；模型归属按短 id 匹配渠道，其它渠道模型迁出（各自渠道的 provider 接管）
- **展开**：每供应商的模型全部补入 models 数组；**模型筛选**：openrouter/opencode 渠道只补**免费模型**（id 含 `:free`/`-free`/`/free`），其它渠道**全量同步**；**模型 displayName 统一为 `{渠道显示名} - {模型名}` 格式**（如 `NewAPI - Sense DeepSeek Latest Flash`、`Sense - DeepSeek V4 Flash`；模型名已以渠道名开头则去重，如 amd 的 `AMD DeepSeek V4 Flash` → `AMD - DeepSeek V4 Flash`）
- **模型 id 保持 pi 原样**：不得擅自添加任何前缀（sense 渠道的 `deepseek-v4-flash` 就是 `deepseek-v4-flash`，不写 `sense/deepseek-v4-flash`；newapi 渠道的 `amd/deepseek-latest-flash` 本身带前缀则原样保留）；当前选中模型 `model` 字段同样用 pi 原样 id
- `apiKey`：**写死实值**（qoder-cn 不支持 env 引用），每 provider 只写归属渠道的 env 值
- 顶层 `baseUrl`/`type`/`protocol`/`authType` 同步时**不动**；`model`（当前选中）用 pi 原样 id（允许去误加前缀规范化 + **版本族升级**，见下条）；`displayName` 在 baseUrl 匹配/新建时更新为渠道显示名，弱匹配时已有值保留（空值补充）
- **默认模型版本族规则（`model` 字段）**：同族（同一产品的不同版本号）模型存在更高版本时，`model` 自动取**同族最高版本**——如渠道 models 含 `agnes-2.0-flash`/`agnes-2.5-flash`/`agnes-3.0-flash` 而 `model` 为 `agnes-2.5-flash` 时，应升级为 `agnes-3.0-flash`。族键提取：模型 id 取**最后一个 `/` 后的段**（无 `/` 取全段）小写后提取**开头连续字母**（`^[a-z]+`，提取不到用整段，如 `agnes-2.5-flash` → `agnes`、`qwen3.8-27b` → `qwen`）；版本号 = 该段**首个数字串**（`2.5` → `(2,5)`，无数字 → 空元组视为最低）。同版本或均无版本号一律不动（幂等）；`model` 为空时取首个模型同族的最高版本

共同要点：
- opencode/dsh/omp 三工具的 apiKey 均为环境变量引用（非明文），同步时保留目标现有引用，只合并 models（保留现有 + 补 pi 缺失）；**qoder-cn 例外：apiKey 写死实值**
- **baseURL / kind（兼容模式，opencode 为 npm、dsh/omp 为 api、qoder-cn 为 type/protocol/authType/baseUrl）：不更新已有值**，仅当目标缺失/为空时补入——zcode 补 pi 的明文 baseURL 与映射后的 kind；opencode 补 `{env:XXX_BASE_URL}` 占位符（由 apiKey 占位符推导）；dsh/omp 补 pi 的 baseURL 与 api；qoder-cn 顶层字段（baseUrl/type/protocol/authType/displayName/model）一律不动，只合并 models 数组与更新 apiKey
- 匹配渠道：同名优先，规范化兜底（如 `cloudflare-workers-ai`）；opencode 无 v2ex 时正确跳过
- 写回：JSON 用 `json.dump(indent=2, ensure_ascii=False)`，YAML 用 `yaml.safe_dump(sort_keys=False, allow_unicode=True, default_flow_style=False)`；校验断言只允许 models 新增、apiKey 更新与 baseURL/kind 空值补充

### 其他工具
让用户提供配置文件路径与结构，遵循该工具现有格式。

**写入后必须校验**：JSON 用 `python3 -m json.tool`，YAML 用 `python3 -c "import yaml;yaml.safe_load(open(...))"`。

> **是否写入、写入哪些工具由用户决定，不要擅自修改任何配置文件。**

## 注意事项

- **开工前必须确认渠道、筛选方式和目标工具**，不要擅自假设。
- 不要只依赖 `free` 标签，若渠道提供定价字段，用价格=0 判断更完整。
- 渠道若没有定价字段，要退化到 `free-tag`/`keyword` 并明确告知用户。
- 不要跳过连通性测试，很多"免费"模型实际不可用。
- 报告给用户的免费清单必须是**实测可用**的，不可用的一律列入剔除原因。
- 写入多工具配置时，务必匹配各工具（pi/omp/opencode/dsh/zcode/qoder-cn）不同的结构格式，并校验。
- dsh 的 models 元素只含 `id`，且路径是 `llm-pi-ai.providers.{渠道}`，不要与 pi 的 `providers.{渠道}` 混淆。
- zcode 的渠道 key 是 UUID（自定义）或 `builtin:xxx`（内置），`options.apiKey` 为明文，`models` 是对象 map（key=模型 id，value=含 name/limit/zcode 的对象），与 pi/omp/dsh 的数组结构不同；`kind: anthropic` 的渠道无 `/models` 端点，模型列表从配置读取。
- qoder-cn 的渠道 key 是 `qoder-custom-{UUID}`，`apiKey` 为明文且位于渠道顶层（非 zcode 的 `options` 内），`models` 是数组、id 字段名为 `model`，`baseUrl` 是顶层小写 l 形式——与 zcode 的 `options.apiKey`/`options.baseURL`/models map、dsh 的 `baseURL` 全大写均不同；每渠道独立 provider + 独立密钥 + 独立模型（模型归属按短 id 匹配渠道，其它渠道模型迁出），`baseUrl`/`type`/`protocol`/`authType` 不动；`model`（当前选中）随同步做**版本族升级**：id 末段（`/` 后）开头连续字母为族键、首个数字串为版本号，同族存在更高版本时自动改用最新版（`agnes-2.5-flash` → `agnes-3.0-flash`）。
- 模型筛选与显示：openrouter/opencode 渠道只补**免费模型**（id 含 `:free`/`-free`/`/free`），其它渠道全量同步；kilo/openrouter 渠道同步到 zcode/dsh/qoder-cn 时改从**上游提取免费模型**（`scripts/fetch_free.py`，须同时满足：free 标签或价格为 0、**最近一年内更新**、**context 存在时 >100K**，剔除图像/视频类）；**opencode 渠道不同步**（上游价格数据不正确）；模型 displayName/name 统一为 **`{渠道显示名} - {模型名}`** 格式（如 `NewAPI - Sense DeepSeek Latest Flash`、`Sense - DeepSeek V4 Flash`，模型名已含渠道名则去重）。
- 同步/写入前先做幂等核对（缺失比对），0 缺失时无写入，避免无意义重写文件。
- 环境变量名正则须含数字（`[A-Z0-9_]+`）；bash 传参用 heredoc 避免 `\$`/`\"` 转义被吞；写回前备份、写回后对比备份断言只动了目标字段。
- 写入明文密钥后报告**绝不回显密钥内容**，只报告长度/变化状态。
- 涉及写入配置时先让用户决定，不要擅自修改。