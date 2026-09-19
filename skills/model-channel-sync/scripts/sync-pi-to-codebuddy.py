#!/usr/bin/env python3
"""pi → codebuddy 全量同步（展开式：pi 渠道×模型 → codebuddy 逐模型条目，apiKey 明文实值）。

用法:
    python3 scripts/sync-pi-to-codebuddy.py

按需修改下方 PI_PATH / CB_PATH。
codebuddy 与 zcode/dsh/omp 等平台的结构根本不同：
- pi 是「渠道(provider) 下挂 models 数组，共享一次 baseUrl/apiKey」；
- codebuddy 是「models 扁平数组，每个条目都是一个独立模型」，自带 id/name/vendor/url/apiKey
  及 supports* 能力字段，无渠道层级。

规则：
- 展开：pi 每个渠道的每个模型 → 一条 codebuddy 条目；vendor = 渠道显示名；
  url = 渠道 baseUrl 规范化（见 url 规则）；apiKey = **写死明文实值**（由 pi 的
  !echo -n "$VAR" 解析环境变量名后取其实值，与 qoder 一致；env 未设置则写空并在报告注明）
- 匹配现有条目：先精确 id，再 url+id，再规范化 id；已有条目若为 ${VAR} 变量引用则一并
  转换为明文实值（同一 env 名解析），已是明文的保留不动；其它字段以 pi 为权威值（url/vendor/name/supports*）
- 同模型多渠道去重：codebuddy 扁平数组中 id 必须唯一；同模型在 pi 多渠道重复时按渠道
  优先级（PRIORITY，sense/amd 最高，openrouter/kilo 最低）只保留一条，避免重复
- 手工条目（pi 无对应）原样保留，只增不删
- url 规则：baseUrl 去尾斜杠；若已以 /chat/completions 结尾则原样保留，否则拼接
  /chat/completions（codebuddy 文档要求 url 必须含完整 /chat/completions 路径）
- supportsImages：pi 模型 input 含 image 或 id 名含 vision/vl 时为 true
- supportsReasoning：pi 模型 reasoning 为 true 时为 true
- supportsToolCall：默认 true
- useCustomProtocol：默认 false
幂等可重复执行；自动备份（.bak-YYYYMMDD）并断言校验；密钥不回显（只报告变量名/长度）。
"""
import json, re, os, shutil, datetime, fetch_free

PI_PATH = os.path.expanduser('~/.pi/agent/models.json')
CB_PATH = os.path.expanduser('~/.codebuddy/models.json')
# kilo/openrouter 渠道不走 pi models 基准，改从上游 API 提取免费模型（与其它平台一致）
UPSTREAM_FREE = ('kilo', 'openrouter')
# 不同步的渠道（pi 中存在但明确排除，如 opencode 上游价格数据不正确）
SKIP_CHANNELS = ('opencode',)
# 渠道优先级：同模型在多渠道重复出现时，优先级高的渠道胜出（避免 codebuddy 扁平数组中 id 重复）
PRIORITY = {
    'sense': 1, 'amd': 2, 'hyper': 3, 'colab': 4, 'inferx': 5,
    'newapi': 6, 'cloudflare-workers-ai': 7, 'agnes': 8,
    'v2ex': 9, 'poolside': 10, 'anyapi': 11, 'tokenrouter': 12,
    'openrouter': 13, 'kilo': 14,  # 上游免费渠道优先级最低（模型与付费渠道重复）
}

# 渠道名 → codebuddy vendor 显示名（缺省用渠道名首字母大写）
VENDOR_NAME = {}


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def vendor_of(pname):
    if pname in VENDOR_NAME:
        return VENDOR_NAME[pname]
    return pname[0].upper() + pname[1:]


def make_url(baseUrl):
    """codebuddy url 必须含 /chat/completions 完整路径。"""
    u = (baseUrl or '').rstrip('/')
    if u.endswith('/chat/completions'):
        return u
    return u + '/chat/completions'


def build_name(vendor, model_name, model_id):
    """codebuddy name 统一为 {vendor} - {模型名} 格式。
    例：vendor=OpenRouter, model_name=Inkling Small (Free) → "OpenRouter - Inkling Small (Free)"
    去重：pi 的模型 name 本身已带渠道前缀时（如 "AMD DeepSeek V4 Flash"、"InferX Devstral 2 123B..."），
    去掉模型名中的 vendor 前缀后再拼接，避免 "AMD - AMD DeepSeek..." 式重复。"""
    if not vendor or not model_name:
        return model_name
    v = re.sub(r'\s+', ' ', vendor).strip()
    m = model_name
    # 模型名已以 vendor 开头（忽略大小写）→ 去掉该前缀，避免重复
    m_stripped = re.sub(r'^' + re.escape(v) + r'[\s\-]*', '', m, flags=re.I).strip()
    if m_stripped and m_stripped != m:
        m = m_stripped
    return f"{v} - {m}" if v else m


def env_name_of(apiKey):
    """pi 的 !echo -n "$VAR" → VAR；其它形式返回 None。"""
    if not apiKey:
        return None
    m = re.search(r'!echo -n "\$([A-Z0-9_]+)"', apiKey)
    if m:
        return m.group(1)
    return None


def env_value_of(apiKey):
    """pi 的 !echo -n "$VAR" → 环境变量实值；无法解析或未设置返回 None。"""
    name = env_name_of(apiKey)
    if name is None:
        return None
    return os.environ.get(name)


def resolve_existing_key(key, env):
    """现有条目 apiKey 规范化为明文实值：${VAR} 变量引用解析为实值；明文原样保留。
    返回 (value, converted)。VAR 与当前渠道 env 名不同条目（用户自定义）按条目内变量名解析。"""
    k = (key or '').strip()
    m = re.fullmatch(r'\$\{([A-Z0-9_]+)\}', k)
    if m:
        return os.environ.get(m.group(1), ''), True  # 变量引用 → 明文实值（未设置则为空）
    return key, False  # 已是明文或空，保留


stamp = datetime.date.today().strftime('%Y%m%d')
shutil.copy(CB_PATH, CB_PATH + '.bak-' + stamp)
bak = json.load(open(CB_PATH + '.bak-' + stamp))

pi = json.load(open(PI_PATH))
cb = json.load(open(CB_PATH))
models = cb.get('models', [])
by_id = {m['id']: m for m in models if 'id' in m}
by_url_id = {(m.get('url'), m.get('id')): m for m in models}

out = []
added, kept, dropped = 0, 0, 0
seen = set()
best = {}  # 规范化 id → 优先级最高的条目（同模型多渠道时去重）

# 预建规范化 id → 现有条目索引（用于 id 规范化匹配：现有条目 qwen38-flash-next 对应 pi qwen3.8-flash-next）
by_norm_id = {}
for m in models:
    by_norm_id.setdefault(norm(m.get('id', '')), m)

for pname, pdata in pi['providers'].items():
    if pname in SKIP_CHANNELS:
        out.append(f'跳过 {pname}: 不同步（价格数据不正确）')
        continue
    env = env_name_of(pdata.get('apiKey'))
    env_val = env_value_of(pdata.get('apiKey'))
    url = make_url(pdata.get('baseUrl'))
    vendor = vendor_of(pname)
    # 模型源：kilo/openrouter 从上游提取免费模型，其它渠道用 pi models
    if pname in UPSTREAM_FREE:
        try:
            items = fetch_free.fetch_free_models(pname)
        except Exception as e:
            items = pdata.get('models', [])
            out.append(f'{pname}: 上游提取失败（{e}），回退 pi models')
    else:
        items = pdata.get('models', [])
    for m in items:
        mid = m['id']
        seen.add(norm(mid))
        raw_name = m.get('name') or m['id']
        name = build_name(vendor, raw_name, mid)
        img = ('image' in m.get('input', [])) or bool(re.search(r'vision|/vl', mid, re.I))
        reasoning = bool(m.get('reasoning'))
        entry = {
            'id': mid,
            'name': name,
            'vendor': vendor,
            'url': url,
            'apiKey': env_val or '',
            'supportsToolCall': True,
            'supportsImages': img,
            'supportsReasoning': reasoning,
            'useCustomProtocol': False,
        }
        # 匹配现有条目（先精确 id，再 url+id，再规范化 id）
        existing = by_id.get(mid) or by_url_id.get((url, mid)) or by_norm_id.get(norm(mid))
        if existing:
            # 现有条目（含自定义 id 变体，如 qwen38-flash-next），只同步 pi 权威字段
            old_key = existing.get('apiKey', '')
            new_key, converted = resolve_existing_key(old_key, env)
            entry['apiKey'] = new_key
            # 现有条目的额外字段（如 maxInputTokens/maxOutputTokens、自定义 id）保留
            for k, v in existing.items():
                if k not in entry:
                    entry[k] = v
            if existing.get('id') != mid:
                entry['id'] = existing['id']  # 保留现有自定义 id 变体
            new_entry = dict(entry)
            if existing.get('id') != mid:
                new_entry['id'] = existing['id']  # 保留现有自定义 id 变体
            pri = PRIORITY.get(pname, 99)
            cur = best.get(norm(mid))
            if cur is None or pri < cur[0]:
                best[norm(mid)] = (pri, new_entry)
            kept += 1
            kstat = '密钥 ${VAR}→明文' if converted else '密钥明文保留'
            status = f"保留现有({kstat}，id: {existing['id']})" if existing.get('id') != mid else f'保留现有({kstat})'
        else:
            pri = PRIORITY.get(pname, 99)
            cur = best.get(norm(mid))
            if cur is None or pri < cur[0]:
                best[norm(mid)] = (pri, entry)
            added += 1
            status = '新增(明文实值)' if env_val else '新增(无 env, 密钥空缺)'
        out.append(f'{pname}/{mid}: {status}')

new_models = [e for _, e in sorted(best.values(), key=lambda x: (x[0], norm(x[1]['id'])))]
dup = len(best) < kept + added
if dup:
    out.append(f'去重: 同模型多渠道 {kept + added} 条 → 保留优先级最高的 {len(best)} 条')

# 现有但 pi 中已不存在的条目：保留（合并式，不删用户手工条目），仅报告
kept_handmade = []
for m in models:
    if norm(m.get('id', '')) not in seen:
        kept_handmade.append(m)
        out.append(f'保留手工条目 {m["id"]}（pi 中无对应，原样不动）')

cb['models'] = new_models + kept_handmade
if 'availableModels' in cb:
    cb['availableModels'] = [m['id'] for m in cb['models']]

tmp = CB_PATH + '.tmp'
with open(tmp, 'w') as f:
    json.dump(cb, f, indent=2, ensure_ascii=False)
    f.write('\n')

# 校验：只允许 models 条目变化（新增/字段更新/保留手工条目），不删任何现有条目（含 id 规范化等价）
bak_ids = {m.get('id') for m in bak.get('models', [])}
new_ids = {m.get('id') for m in cb['models']}
new_norms = {norm(x) for x in new_ids}
removed = {x for x in bak_ids - new_ids if norm(x) not in new_norms}
assert not removed, f'断言失败：删除了现有条目 {removed}（同步只增不删）'
# 现有条目 apiKey 允许 ${VAR}→明文实值转换；已是明文的不得改动
bak_key = {m['id']: m.get('apiKey', '') for m in bak.get('models', [])}
for m in new_models:
    if m['id'] in bak_key:
        b = (bak_key[m['id']] or '').strip()
        if re.fullmatch(r'\$\{[A-Z0-9_]+\}', b):
            continue  # 变量引用已被转换为明文实值，允许
        assert m.get('apiKey', '') == bak_key[m['id']], f"断言失败：现有明文条目 {m['id']} 的 apiKey 被改动"
shutil.move(tmp, CB_PATH)
json.load(open(CB_PATH))  # JSON 格式校验
print(f'校验通过：新增 {added} / 保留 {kept}（apiKey 统一明文实值；${{VAR}} 条目已转换）')
for line in out:
    print(line)
