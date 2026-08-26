---
name: free-models-extract
description: >-
  从任意 AI 模型渠道（provider）提取真正可用的免费/零价模型清单，并可更新到多个 agent 工具（pi、omp、opencode、dsh 等）的配置文件。
  凡是用户提到"获取/提取/列出/查看 XX 渠道免费模型"、"从价格判断免费模型"、"查价格为零的模型"、
  "有哪些免费模型可用"、"给 XX 渠道加免费模型"、"这个免费模型能用吗"、"把模型更新到 pi/omp/opencode/dsh"时，都应使用此技能。
  技能通用性强：支持配置文件中所有 OpenAI 兼容渠道（openrouter、kilo、opencode、newapi、nvidia、atomgit 等）。
  使用前需用户指定：①目标渠道，②筛选方式（按价格=0 / free 标签 / 关键词等）。技能会抓取 → 筛选 → 连通性实测 → 剔除不可用 → 给出结论并可写入多工具配置。
---

# 免费模型提取与多工具更新（通用）

本技能从**任意 AI 模型渠道**提取**真正可用**的免费/零价模型，并支持将结果更新到多个 agent 工具的配置文件。核心价值：很多模型看似免费（带 `free` 标签或定价为 0），但实际因地区限制、鉴权失败、上游故障而不可用。技能完成「抓取 → 筛选 → 实测 → 结论 → 可选写入多工具」的完整闭环。

## 触发时机

当用户希望了解或配置某渠道的免费模型、或把模型同步到工具配置时使用，典型表述：
- "从 XX 获取免费模型列表供我选择"
- "从价格中判断哪些是免费模型"
- "XX 渠道有哪些免费模型可用"
- "给 pi/omp 的 XX 渠道添加免费模型"
- "把这个免费模型更新到 opencode / pi / omp / dsh"
- "这个免费模型能用吗 / 测试一下这个模型"

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
- 其他工具：让用户提供配置文件路径与结构

> 默认查询/提取只需渠道+筛选方式，写入配置时才确认目标工具。
> 注意：dsh 的渠道配置并不来自 pi 的 `models.json`，其结构与 pi 不同（见「第 1 步」和「dsh」章节），读取 baseUrl/apiKeyEnv 时应以 `~/.dsh/settings.yaml` 为准。

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
- 写入多工具配置时，务必匹配各工具（pi/omp/opencode/dsh）不同的结构格式，并校验。
- dsh 的 models 元素只含 `id`，且路径是 `llm-pi-ai.providers.{渠道}`，不要与 pi 的 `providers.{渠道}` 混淆。
- 涉及写入配置时先让用户决定，不要擅自修改。