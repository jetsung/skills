---
name: model-channel-sync
description: >-
  管理 AI 模型渠道（provider）配置：①提取真正可用的免费/零价模型（抓取 → 筛选 → 连通性实测 → 剔除不可用 → 给出结论）；
  ②以 pi 等平台配置为基准，同步/更新渠道、模型、APIKEY 到多个 agent 工具（pi、zcode、dsh、omp、opencode、qoder、codebuddy 等）的配置文件。
  凡用户提到"获取/提取/列出 XX 渠道免费模型"、"从价格判断免费模型"、"查价格为零的模型"、"有哪些免费模型可用"、
  "给 XX 渠道加免费模型"、"这个免费模型能用吗/测试一下"、"把模型更新到 pi/omp/opencode/dsh/zcode/qoder/codebuddy"、
  "以 pi 为基准更新 XX 渠道"、"同步渠道/模型/APIKEY 到 XX"、"更新 XX 的 APIKEY"时，都应使用此技能。
  支持配置文件中所有 OpenAI 兼容渠道（openrouter、kilo、opencode、newapi、nvidia、atomgit 等）。
compatibility: Requires curl, python3 (with PyYAML), and network access to provider APIs.
---

# 模型渠道配置管理（免费提取与多工具同步）

本技能管理**AI 模型渠道配置**：从任意渠道提取**真正可用**的免费/零价模型，并将渠道、模型、密钥同步到多个 agent 工具的配置文件。核心价值：很多模型看似免费（带 `free` 标签或定价为 0），但实际因地区限制、鉴权失败、上游故障而不可用。技能完成「抓取 → 筛选 → 实测 → 结论 → 可选写入/同步多工具」的完整闭环。

**目录结构**：
- `scripts/` — 各工具同步脚本（幂等，自动备份+断言校验）与上游免费模型提取脚本 `fetch_free.py`
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
| pi | `~/.pi/agent/models.json` | `references/pi.md` |
| omp (Oh My Pi) | `~/.omp/agent/models.yml` | `references/omp.md` |
| opencode | `~/.config/opencode/opencode.json` | `references/opencode.md` |
| dsh (DeepSeek Harness) | `~/.dsh/settings.yaml` | `references/dsh.md` |
| zcode | `~/.zcode/v2/provider_config.json` | `references/zcode.md` |
| qoder | `~/.qoder/settings.json`（国外版）与 `~/.qoder-cn/settings.json`（国内版） | `references/qoder.md` |
| codebuddy | `~/.codebuddy/models.json` | `references/codebuddy.md` |
| 其他 | 用户提供路径与结构 | 遵循该工具现有格式 |

> 默认查询/提取只需渠道+筛选方式，写入配置时才确认目标工具。
> qoder 是同一软件的国外版（`~/.qoder`）与国内版（`~/.qoder-cn`），结构相同；**按目录存在情况同步，都存在则都同步**。
> 注意：dsh 的渠道配置不来自 pi 的 `models.json`，读取 baseUrl/apiKey 应以 `~/.dsh/settings.yaml` 为准；zcode 同理。

## 依赖

- 目标渠道的 `baseUrl` 与 `apiKey`（通常从 pi 配置文件读取；若写入目标是 dsh，则从 `~/.dsh/settings.yaml` 读取）
- `curl` 和 `python3`

## pi 数据缓存（一次提取并验证，多平台共用）

各 `sync-pi-to-*.py` 脚本**不直接读 pi**，也不各自做渠道检查，而是统一经 `scripts/pi_cache.py` 读取缓存 `~/.cache/model-channel-sync/pi-models.json`。**缓存即检查结果**——渠道可用性验证在缓存生成时一次性完成：

- **提取即检查**：生成缓存时对每个渠道调 `GET {baseUrl}/models`（apiKey 从 pi 解析为实值）：
  - **渠道不通**（鉴权失败/连接失败/响应异常）→ 该渠道**不写入缓存**；同步脚本从缓存取数时自然跳过此渠道，不创建 provider、不写密钥、不合并模型
  - **可用且 /models 返回模型列表** → 原装数据入缓存，并记入 `models_api[渠道] = [实时模型 id 列表]`
  - **可用但无 /models 接口**（HTTP 405、端点不返回 data 列表等）→ 记入 `no_models_api` 列表；同步时**直接以 pi 写死的模型列表为准**，不做实时过滤
  - **中转站渠道**（`pi_cache.py` 的 `FORCE_NO_MODEL_FILTER`，当前为 openrouter、nvidia）：判定依据是 pi 模型条目的 **`vendor` 字段值（不区分大小写）** 命中名单（渠道 key 命中也兜底生效），如某渠道模型的 `vendor` 为 `Openrouter` 即视为中转站。此类渠道 `/models` 可读但模型列表与 pi 不一一对应（聚合/改名），**按 no_models_api 方式处理**——同步时直接以 pi 写死的模型列表为准（不做失效过滤），**参数值（contextWindow/maxTokens/input 等）仍从缓存原装数据取**
- **模型失效过滤**：同步时 `/models` 可读的渠道只添加实时列表中仍存在的模型——pi 有但实时缓存中已不存在的模型**不添加**（`pi_cache.filter_models`，剔除的在报告中注明）
- **数据权威顺序**：渠道与模型**以 pi 为准**（哪些渠道、哪些模型），但**数据内容以缓存为准**（缓存是检查后的快照：不可用渠道已被剔除、失效模型已被标记）
- **原装数据**：可用渠道的 providers 段原样保存（含 contextWindow/maxTokens/input/cost 等，不裁剪），支持参数的平台直接取用
- **失效策略**：pi 文件 mtime 变化即重新提取（**重新做渠道检查**）；`PI_CACHE_TTL`（秒）强制过期重提；`python3 scripts/pi_cache.py` 手动刷新并查看检查结果（可用/不可用/无 /models 接口渠道清单）
- 手动单渠道自检：`python3 scripts/channel_check.py <渠道名> <baseUrl> <apiKey> ...`

## 各平台模型配置官方文档（速查）

| 平台 | 官方文档 URL |
|------|--------------|
| pi | https://pi.dev/docs/latest/models |
| omp (Oh My Pi) | https://omp.sh/docs/custom-models |
| opencode | https://opencode.ai/docs/models 、https://opencode.ai/docs/providers |
| dsh（DeepSeek Harness） | https://deepseek-harness.github.io/deepseek-harness/guide/providers |
| zcode | —（无官方文档，以 `references/zcode.md` 为准） |
| qoder | —（providers 段为 BYOK 存储，以 `references/qoder.md` 为准） |
| codebuddy | https://www.codebuddy.cn/docs/cli/models |

> 需要核对某平台最新配置结构时，直接抓取对应 URL（注意：omp 文档页面为 JS 渲染，普通抓取只返回空壳，需从页面 JS 打包资源中提取文本；pi/codebuddy 可直接抓取）。

## 工作流程（提取免费模型）

### 第 1 步：读取渠道配置

- **pi**：从 `~/.pi/agent/models.json` 读取 `baseUrl` 和 `apiKey`；`apiKey` 形如 `!echo -n "$ENV_VAR"`，需解析出环境变量名并取值（详见 `references/pi.md`）
- **dsh**：从 `~/.dsh/settings.yaml` 读取 `llm-pi-ai.providers.{渠道}` 的 `baseURL` 与 `apiKeyEnv`（详见 `references/dsh.md`）
- **zcode**：从 `~/.zcode/v2/provider_config.json` 读取渠道 `config.api.baseUrl` 与 `config.access.apiKey`（明文；详见 `references/zcode.md`）
- **qoder**：从 `~/.qoder/settings.json`（或 `~/.qoder-cn`）读取 `providers.{渠道key}` 的 `baseUrl` 与 `apiKey`（明文；详见 `references/qoder.md`）

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
| opencode | `references/opencode.md` | `provider.{渠道}.models` 对象 map（key=id，value `{id, name, family}`） | 保留 `{env:XXX}` 占位符 |
| dsh | `references/dsh.md` | `llm-pi-ai.providers.{渠道}.models` 列表仅 `id` | 保留 `apiKeyEnv` 变量名 |
| zcode | `references/zcode.md` | 规则式（`personalModelIds`/`modelOrder` + `providerModelRules`） | **写死明文实值**（不支持 env 引用） |
| qoder | `references/qoder.md` | `providers.{qoder-custom-{UUID}}.models` 数组（id 字段名为 `model`） | **写死明文实值**（渠道顶层） |
| codebuddy | `references/codebuddy.md` | 扁平 models 数组（无渠道层级，每模型独立条目） | **写死明文实值**（现有 `${VAR}` 条目一并转换） |

**共同规则：**
- 只写**用户级（全局）**配置，**禁止修改项目级/工作区内的配置文件**（pi/omp/opencode/dsh/zcode/qoder/codebuddy 全部适用）
- 只合并/新增模型条目，保留已有条目不变；同步为**合并式（只增不删）**，上游下架的模型不会自动移除，需清理时手动处理
- 若 API 返回的模型包含 maxTokens、contextWindow 等参数字段，同步写入时一并更新到配置文件中（字段映射见各参考文件）
- 渠道级字段（baseURL/kind/compat 等）：已有值不更新，仅目标缺失/为空时补入

### 多工具全量同步（pi 为基准）

按目标工具选脚本（均在 `scripts/` 下，幂等可重复执行，自动备份+断言校验；执行前按需修改脚本顶部路径/别名变量）：

```bash
python3 scripts/sync-pi-to-opencode.py
python3 scripts/sync-pi-to-dsh.py
python3 scripts/sync-pi-to-omp.py
python3 scripts/sync-pi-to-zcode.py
python3 scripts/sync-pi-to-qoder.py
python3 scripts/sync-pi-to-codebuddy.py
```

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

- **AMD 渠道全量同步**：不区分免费/付费，同步时全量写入所有模型
- **Sense 渠道版本族精简**：只保留每个系列的最新版模型（如 `sensenova-6.7-flash-lite` 和 `sensenova-6.8-flash-lite` 只保留后者）；同系列（id 含相同前缀）按版本号排序取最高
- **模型筛选**：openrouter/opencode 渠道只补**免费模型**（id 含 `:free`/`-free`/`/free`），其它渠道全量同步
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
  - dsh 的 models 元素只含 `id`，路径是 `llm-pi-ai.providers.{渠道}`（`baseURL` 全大写），不要与 pi 的 `providers.{渠道}` 混淆
  - zcode 的 `access.apiKey`/qoder 的顶层 `apiKey` 均为**明文实值**，不支持任何 env 引用形式；zcode 渠道条目与模型条目字段集合**固定**，不可添加额外字段
  - qoder 的 id 字段名为 `model`（非 pi/dsh 的 `id`），`baseUrl` 顶层小写 l；渠道 key 为 `qoder-custom-{UUID}`，每渠道独立 provider + 独立密钥 + 独立模型
  - omp 的 `apiKey` 是 env 变量名裸形式（不带 `$`），与 pi 的 `!echo -n "$VAR"`、opencode 的 `{env:XXX}` 均不同
  - zcode 的 `api.type: anthropic-messages` 渠道无 `/models` 端点，模型列表从 `personalModelIds` 读取
- 环境变量名正则须含数字（`[A-Z0-9_]+`）；长脚本用 heredoc/独立脚本文件传给 python3，**不要用 bash 双引号 `-c "..."`**（会吞掉 `\$`/`\"` 转义导致正则失效）。
- 同步/写入前先做幂等核对（缺失比对），0 缺失时无写入，避免无意义重写文件；写回前备份、写回后对比备份断言只动了目标字段。
- 写入明文密钥后报告**绝不回显密钥内容**，只报告长度/变化状态。
- 写入明文密钥的配置文件（zcode/qoder/codebuddy）切勿提交到版本库。
