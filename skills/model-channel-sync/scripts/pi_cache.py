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
- **失效策略**：pi 文件 mtime 变化即重新提取（重新做渠道检查）；`PI_CACHE_TTL`（秒）可
  强制过期重提；`python3 scripts/pi_cache.py` 手动刷新（此时会重新请求各渠道 /models）

返回结构（load()）:
    {
      'providers':      {渠道: 原装 provider 数据}   # 仅含可用渠道
      'models_api':     {渠道: [实时模型 id]}        # /models 可读列表的渠道
      'no_models_api':  [渠道]                       # 无 /models 接口的渠道
    }
"""
import json, os, sys, time

sys.dont_write_bytecode = True  # 本模块被导入，不生成 __pycache__

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import channel_check

PI_PATH = os.path.expanduser('~/.pi/agent/models.json')
CACHE_PATH = os.path.expanduser('~/.cache/model-channel-sync/pi-models.json')

# 中转站 vendor 名单（不区分大小写）：pi 模型条目 vendor 字段命中（或渠道 key 命中，兜底）时，
# 该渠道按 no_models_api 方式处理——/models 可读但模型列表与 pi 不一一对应（聚合/改名），
# 同步时直接以 pi 写死的模型列表为准（不做实时失效过滤），参数值仍从缓存原装数据取
FORCE_NO_MODEL_FILTER = ('openrouter', 'nvidia')


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


def filter_models(cached, pname, items):
    """同步时模型过滤：/models 可读的渠道剔除实时列表中已不存在的模型（模型已失效不添加）；
    无 /models 接口的渠道（no_models_api）原样返回（以 pi 写死列表为准）。
    返回 (过滤后 items, 剔除的模型 id 列表)。"""
    live = (cached.get('models_api') or {}).get(pname)
    if live is None:
        return items, []  # 无 /models 接口渠道或无记录 → 不过滤
    live = set(live)
    dropped = [m['id'] for m in items if m.get('id') not in live]
    return [m for m in items if m.get('id') in live], dropped


def _extract():
    """全量读取 pi models.json，逐渠道做可用性检查后组装缓存数据。"""
    with open(PI_PATH) as f:
        pi = json.load(f)
    providers, models_api, no_models_api, unavailable = {}, {}, [], {}
    for pname, pdata in pi.get('providers', {}).items():
        r = channel_check.check(pname, pdata.get('baseUrl') or '',
                                channel_check.pi_key_val(pdata.get('apiKey')))
        if not r['ok']:
            unavailable[pname] = r['reason']  # 渠道不通 → 不入缓存
            continue
        ids = r.get('model_ids') or []
        if ids and not _is_relay(pname, pdata):
            models_api[pname] = ids      # /models 可读 → 记录实时模型列表
        else:
            # 无 /models 接口，或中转站渠道（vendor 命中 FORCE_NO_MODEL_FILTER）→ 以 pi 写死列表为准
            no_models_api.append(pname)
        providers[pname] = pdata         # 原装数据（不裁剪字段）
    return {'providers': providers, 'models_api': models_api,
            'no_models_api': no_models_api, 'unavailable': unavailable}


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
