#!/usr/bin/env python3
"""pi 模型数据缓存层：一次提取（含渠道可用性验证），多平台同步共用。

各 sync-pi-to-*.py 不再各自直读 pi 的 models.json，而是经本模块读取缓存
~/.cache/model-channel-sync/pi-models.json。缓存生成时已完成渠道检查，**缓存即检查结果**：

- **渠道检查前置**：提取时对每个渠道调 GET {baseUrl}/models 验证可用性：
  - 渠道不通（鉴权失败/连接失败/响应异常）→ **不写入缓存**（同步时自然跳过该渠道）
  - 渠道可用且 /models 返回模型列表 → 记入 `models_api[渠道] = [实时模型 id]`（供同步时过滤失效模型）
  - 渠道可用但无 /models 接口（HTTP 405 / 端点不返回 data 列表）→ 记入 `no_models_api` 列表
    （同步时直接以 pi 写死的模型列表为准，不做实时过滤）
- **原装数据**：可用渠道的 providers 段原样保存（含 contextWindow/maxTokens/input/cost 等，
  不裁剪），支持参数的平台直接取用
- **classifier 例外**：type=classifier 的条目（决策模型）原样保留在 providers 中，不参与
  失效/文本/系列/时间过滤；同步到非 pi 平台时默认剔除（那些平台没有 classifier 能力，
  写入会被当聊天模型调用而报错）
- **失效策略**：pi 文件 mtime 变化即重新提取（重新做渠道检查）；`PI_CACHE_TTL`（秒）可
  强制过期重提；`python3 scripts/pi_cache.py` 手动刷新（此时会重新请求各渠道 /models）

返回结构（load()）:
    {
      'providers':      {渠道: 原装 provider 数据}      # 仅含可用渠道
      'models_api':     {渠道: [实时模型 id]}           # /models 可读列表的渠道
      'no_models_api':  [渠道]                          # 无 /models 接口的渠道
      'unavailable':    {渠道: 不可用原因}              # 渠道检查未通过的渠道
      'models_created': {渠道: {模型 id: created}}      # /models 提供的发布时间（可能为空）
    }
"""
import calendar, datetime, json, os, sys, time

sys.dont_write_bytecode = True  # 本模块被导入，不生成 __pycache__

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import channel_check

PI_PATH = os.path.expanduser('~/.pi/agent/models.json')
CACHE_PATH = os.path.expanduser('~/.cache/model-channel-sync/pi-models.json')

# 中转站 vendor 名单（不区分大小写）：pi 模型条目 vendor 字段命中（或渠道 key 命中，兜底）时，
# 该渠道按 no_models_api 方式处理——/models 可读但模型列表与 pi 不一一对应（聚合/改名），
# 同步时直接以 pi 写死的模型列表为准（不做实时失效过滤），参数值仍从缓存原装数据取
FORCE_NO_MODEL_FILTER = ('openrouter', 'nvidia', 'anyapi', 'cli2api')

# Nvidia / AMD / Jiutian 渠道系列约束（默认启用，SKIP_SERIES_FILTER=1 可跳过）：模型 id 以 "/"
# 拆分为 provider/model 后，取 model 部分（转小写）开头的连续字母前缀匹配本名单，命中才同步。
# 如 meta/muse-glimmer-30b → model 前缀 "muse" 命中；DeepSeek-V4-Flash → "deepseek" 命中；
# MiniCPM5-2B → "minicpm" 不命中（剔除）。匹配不区分大小写（全部转小写再比较）。
SERIES_ALLOW = ('minimax', 'mimo', 'glm', 'qwen', 'deepseek', 'kimi', 'step', 'muse', 'hy')
# 应用此约束的渠道 key（不区分大小写）
SERIES_CHANNELS = ('nvidia', 'amd', 'jiutian')

# 时间窗约束（默认启用，SKIP_TIME_FILTER=1 可跳过）：/models 返回的 created 早于最近
# RECENT_MONTHS 个月的模型剔除（"只看近期模型"的要求）。无 created 数据的模型保留——
# 多数国内网关（amd / jiutian 等）不返回发布时间，不能据此判为过期。
TIME_FILTER_CHANNELS = ('nvidia', 'amd', 'jiutian')
RECENT_MONTHS = 9

# classifier（决策模型）例外：pi 模型条目 type 为 classifier 的条目（如 amd 的 d3 / d3-flash /
# Clef）不参与失效/文本/系列/时间过滤——上游 /models 常把它们标为 decision 输出、context_length=0，
# 这些都不代表失效。它们只对 pi（codemode 的 models.classify）有意义，其它平台一律不支持，
# 因此默认剔除（reason 分类器）；keep_classifier=True 时原样保留（pi 自身维护时使用）。
CLASSIFIER_TYPE = 'classifier'


def is_classifier_model(m):
    """pi 模型条目是否为 classifier（决策模型，非聊天模型）。"""
    return isinstance(m, dict) and (m.get('type') or '').strip().lower() == CLASSIFIER_TYPE


def _is_relay(pname, pdata):
    """中转站渠道判定：模型条目 vendor 值（不区分大小写）或渠道 key 命中 FORCE_NO_MODEL_FILTER。"""
    keys = {v.strip().lower() for v in FORCE_NO_MODEL_FILTER}
    if pname.lower() in keys:
        return True
    for m in pdata.get('models', []):
        if isinstance(m, dict) and (m.get('vendor') or '').strip().lower() in keys:
            return True
    return False


def load():
    """返回缓存数据：{'providers', 'models_api', 'no_models_api'}。缓存有效时读缓存，否则重新提取（含渠道检查）。"""
    pi_mtime = os.path.getmtime(PI_PATH) if os.path.exists(PI_PATH) else 0

    cached = _read_cache()
    if cached is not None and cached.get('_pi_mtime') == pi_mtime and _ttl_ok(cached):
        return cached['data']
    data = _extract()
    _write_cache(data, pi_mtime)
    return data


def refresh():
    """强制重新提取（重新做渠道检查）并写缓存。"""
    pi_mtime = os.path.getmtime(PI_PATH) if os.path.exists(PI_PATH) else 0
    data = _extract()
    _write_cache(data, pi_mtime)
    return data


def is_text_model(m):
    """文本能力判定：pi 模型条目 input 缺省默认 ["text"]（视为文本模型）；
    input 存在时必须包含 "text"（视觉模型 ["text","image"] 同样保留），
    纯 image/ocr 等不支持文本输入的模型返回 False。"""
    inp = m.get('input')
    return True if inp is None else 'text' in inp


def series_prefix(mid):
    """模型 id 的系列前缀：以 "/" 拆分为 provider/model 后，取 model 部分转小写
    开头的连续字母。如 meta/muse-glimmer-30b → "muse"；DeepSeek-V4-Flash → "deepseek"。"""
    model = mid.split('/')[-1] if '/' in mid else mid
    s = ''
    for ch in model.lower():
        if ch.isalpha():
            s += ch
        else:
            break
    return s


def series_allowed(mid):
    """系列约束命中判定：model 部分前缀（小写）在 SERIES_ALLOW 名单中返回 True。"""
    return series_prefix(mid) in SERIES_ALLOW


def _months_ago(months, today=None):
    """N 个月前的日期（按自然月回退，月末日期取目标月最后一天）。"""
    today = today or datetime.date.today()
    total = today.year * 12 + (today.month - 1) - months
    year, month = divmod(total, 12)
    month += 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def created_recent(created, months=RECENT_MONTHS):
    """发布时间在最近 N 个月内返回 True。无 created（0/None/非法值）视为未知 → True
    （保留）；支持秒与毫秒时间戳。"""
    if not created:
        return True
    try:
        ts = float(created)
    except (TypeError, ValueError):
        return True
    if ts > 1e11:  # 毫秒时间戳
        ts /= 1000.0
    try:
        d = datetime.date.fromtimestamp(ts)
    except (OverflowError, OSError, ValueError):
        return True
    return d >= _months_ago(months)


def filter_models(cached, pname, items, keep_classifier=False):
    """同步时模型过滤：①/models 可读的渠道剔除实时列表中已不存在的模型（模型已失效不添加）；
    ②剔除不支持文本输入的模型（input 存在且不含 text，如纯 image/ocr 模型）；
    ③Nvidia/AMD/Jiutian 渠道剔除系列不在 SERIES_ALLOW 的模型（model 前缀白名单，
      SKIP_SERIES_FILTER=1 可跳过）；
    ④Nvidia/AMD/Jiutian 渠道剔除 /models 的 created 早于 RECENT_MONTHS 个月的模型
      （无 created 数据保留；SKIP_TIME_FILTER=1 可跳过）；
    无 /models 接口的渠道（no_models_api）不做失效过滤（以 pi 写死列表为准）。

    classifier（type=classifier，决策模型）是例外：①~④ 全部不适用（上游把它们的输出
    标为 decision、context_length=0，均不代表失效）。keep_classifier=True 时原样保留
    （pi 自身）；默认 False 时剔除，因为其它平台没有 classifier 能力，写入会被当聊天模型
    调用而报错。返回 (过滤后 items, 剔除列表)；剔除项为 {id, reason}，
    reason ∈ {'失效','非文本','系列约束','超期','分类器'}。"""
    items = list(items or [])
    classifiers = [m for m in items if is_classifier_model(m)]
    items = [m for m in items if not is_classifier_model(m)]
    live = (cached.get('models_api') or {}).get(pname)
    if live is not None:
        live = set(live)
        items = [m for m in items if m.get('id') in live]
    dropped = []
    for m in items:
        if not is_text_model(m):
            dropped.append({'id': m['id'], 'reason': '非文本'})
    if dropped:
        items = [m for m in items if is_text_model(m)]
    # Nvidia / AMD / Jiutian 系列约束（默认启用；SKIP_SERIES_FILTER=1 显式跳过）
    if pname.lower() in SERIES_CHANNELS and os.environ.get('SKIP_SERIES_FILTER') != '1':
        sdrop = [m['id'] for m in items if not series_allowed(m['id'])]
        if sdrop:
            items = [m for m in items if series_allowed(m['id'])]
            dropped += [{'id': mid, 'reason': '系列约束'} for mid in sdrop]
    # Nvidia / AMD / Jiutian 时间窗约束（默认启用；SKIP_TIME_FILTER=1 显式跳过）
    if pname.lower() in TIME_FILTER_CHANNELS and os.environ.get('SKIP_TIME_FILTER') != '1':
        created_map = (cached.get('models_created') or {}).get(pname) or {}
        tdrop = {m['id'] for m in items
                 if not created_recent(created_map.get(m['id']))}
        if tdrop:
            items = [m for m in items if m['id'] not in tdrop]
            dropped += [{'id': mid, 'reason': '超期'} for mid in tdrop]
    if classifiers:
        if keep_classifier:
            items += classifiers
        else:
            dropped += [{'id': m['id'], 'reason': '分类器'} for m in classifiers]
    return items, dropped

def dropped_note(pname, dropped):
    """把 filter_models 返回的剔除列表格式化为可读文案（带原因）。空列表返回 None。"""
    if not dropped:
        return None
    reason_txt = {'失效': '实时 /models 不再存在', '非文本': '不支持文本输入',
                  '系列约束': '系列不在白名单', '超期': f'发布时间早于 {RECENT_MONTHS} 个月',
                  '分类器': '决策模型（classifier），仅 pi 支持'}
    parts = []
    for d in dropped:
        rid = d['id'] if isinstance(d, dict) else d
        why = reason_txt.get(d.get('reason', '') if isinstance(d, dict) else '', '')
        parts.append(f'{rid}（{why}）' if why else rid)
    return f'{pname}: 剔除模型 {len(dropped)} 个: ' + '、'.join(parts)

# 不得主动添加的渠道（除非用户显式声明，如 ALLOW_NO_AUTO_ADD=1 或渠道在 ALLOW_NO_AUTO_ADD 列表）：
# 同步脚本在目标平台无对应渠道时，禁止自动创建 opencode/openrouter 的 provider。
# 存量/已有 provider 的模型更新不受限；仅限制"新建渠道"动作。
NO_AUTO_ADD_CHANNELS = ('opencode', 'openrouter')


def no_auto_add(pname):
    """渠道是否禁止自动新建 provider（不区分大小写）。
    ALLOW_NO_AUTO_ADD=1 或渠道在 ALLOW_NO_AUTO_ADD 列表时放行（用户显式声明添加）。"""
    if pname.lower() not in NO_AUTO_ADD_CHANNELS:
        return False
    if os.environ.get('ALLOW_NO_AUTO_ADD') == '1':
        return False
    allow = (os.environ.get('ALLOW_NO_AUTO_ADD') or '').lower().split(',')
    return pname.lower() not in [a.strip() for a in allow if a.strip()]


def _extract():
    """全量读取 pi models.json，逐渠道做可用性检查后组装缓存数据。"""
    with open(PI_PATH) as f:
        pi = json.load(f)
    providers, models_api, no_models_api, unavailable = {}, {}, [], {}
    models_created = {}
    for pname, pdata in pi.get('providers', {}).items():
        models = [m['id'] for m in pdata.get('models', []) if isinstance(m, dict) and m.get('id')]
        r = channel_check.check(pname, pdata.get('baseUrl') or '',
                                channel_check.pi_key_val(pdata.get('apiKey')), models=models)
        if not r['ok']:
            unavailable[pname] = r['reason']  # 渠道不通 → 不入缓存
            continue
        ids = r.get('model_ids') or []
        if r.get('model_created'):
            models_created[pname] = r['model_created']  # 发布时间，供时间窗过滤
        if ids and not _is_relay(pname, pdata):
            models_api[pname] = ids      # /models 可读 → 记录实时模型列表
        else:
            # 无 /models 接口，或中转站渠道（vendor 命中 FORCE_NO_MODEL_FILTER）→ 以 pi 写死列表为准
            no_models_api.append(pname)
        providers[pname] = pdata         # 原装数据（不裁剪字段）
    return {'providers': providers, 'models_api': models_api,
            'no_models_api': no_models_api, 'unavailable': unavailable,
            'models_created': models_created}


def _read_cache():
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None  # 缓存损坏则重建


def _write_cache(data, pi_mtime):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    payload = {'_pi_mtime': pi_mtime, '_cached_at': time.time(), 'data': data}
    tmp = CACHE_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CACHE_PATH)  # 原子写，避免并发/中断产生半截缓存


def _ttl_ok(cached):
    ttl = int(os.environ.get('PI_CACHE_TTL', '0'))
    if ttl <= 0:
        return True  # 默认只按 mtime 失效
    return time.time() - cached.get('_cached_at', 0) < ttl


if __name__ == '__main__':
    data = refresh()
    n = sum(len(p.get('models', [])) for p in data['providers'].values())
    print(f'缓存已更新: {CACHE_PATH}')
    print(f"可用渠道 {len(data['providers'])} 个，模型共 {n} 个（原装字段全量保存）")
    if data['no_models_api']:
        print(f"无 /models 接口渠道（以 pi 列表为准）: {', '.join(data['no_models_api'])}")
    if data['unavailable']:
        print('不可用渠道（未入缓存，同步时跳过）:')
        for ch, why in data['unavailable'].items():
            print(f'  - {ch}: {why}')
