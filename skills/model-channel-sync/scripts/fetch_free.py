#!/usr/bin/env python3
"""上游免费模型提取（kilo / opencode / openrouter 渠道）。

提供 fetch_free_models(channel) -> [{id, name}]：
- 免费判定：id 含 :free/-free//free 标签，或 pricing.prompt/completion 均为 0（含临时免费）
- 剔除图像/视频/音频模型（EXCLUDE 关键词）
- **最近一年内更新**：created/release 时间早于一年前的剔除（无时间数据的模型保留，
  如 kilo 的 kilo-auto/free 是聚合入口非真实模型则按 created=0 剔除——见 _recent 规则）
- **上下文限制**：context 若存在则必须 >100K（无 context 数据的模型保留）
- 结果缓存 ~/.cache/model-channel-sync/free-{channel}.json（1 小时）；
  上游请求失败时回退上次缓存，无缓存则抛异常（由调用方决定回退 pi models）
"""
import json, os, re, time, urllib.request
from datetime import date, datetime, timedelta

BASE = {
    'kilo':       ('https://api.kilo.ai/api/gateway/v1', 'KILO_API_KEY'),
    'opencode':   ('https://opencode.ai/zen/v1', 'OPENCODE_API_KEY'),
    'openrouter': ('https://openrouter.ai/api/v1', 'OPENROUTER_API_KEY'),
}
# 剔除的模型关键词（图像/视频/音频类，不适合编程对话）
EXCLUDE = ('lyria', 'image', 'video', 'whisper', 'tts')
# 上下文门槛：context 存在时必须大于该值
MIN_CONTEXT = 100_000
# 更新时间门槛：最近一年
RECENT_DAYS = 365
CACHE_DIR = os.path.expanduser('~/.cache/model-channel-sync')
CACHE_TTL = 3600


def _is_free(mid, pricing):
    """免费判定：free 标签 或 价格（prompt/completion）均为 0"""
    low = mid.lower()
    if any(x in low for x in EXCLUDE):
        return False
    if ':free' in low or '-free' in low or '/free' in low:
        return True
    p = pricing or {}

    def zero(x):
        try:
            return float(x or 0) == 0
        except (TypeError, ValueError):
            return False
    return zero(p.get('prompt')) and zero(p.get('completion'))


def _recent(created_ts):
    """时间判定：最近一年内更新返回 True；无时间数据返回 False（严格模式）"""
    if not created_ts:
        return False
    return datetime.fromtimestamp(created_ts) >= datetime.now() - timedelta(days=RECENT_DAYS)


def _context_ok(ctx):
    """上下文判定：无数据保留（True），有数据必须 > MIN_CONTEXT"""
    return ctx is None or ctx > MIN_CONTEXT


def _pretty_name(mid):
    """从模型 id 生成显示名：去供应商前缀，token 大小写规范化，free 标签补 (Free) 后缀"""
    short = mid.split('/')[-1]
    is_free = ':free' in short or '-free' in short or '/free' in short
    tokens = [t for t in re.split(r'[-_:]', short) if t and t.lower() != 'free']
    words = []
    for t in tokens:
        if any(c.isdigit() for c in t) and len(t) <= 5:
            words.append(t.upper())
        else:
            words.append(t.capitalize())
    name = ' '.join(words)
    if is_free:
        name += ' (Free)'
    return name


def fetch_free_models(channel):
    """返回渠道上游的免费模型列表 [{id, name}]，带 1 小时缓存与失败回退"""
    if channel not in BASE:
        raise ValueError(f'未知渠道: {channel}')
    base, env = BASE[channel]
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = os.path.join(CACHE_DIR, f'free-{channel}.json')
    if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < CACHE_TTL:
        return json.load(open(cache))
    headers = {'User-Agent': 'model-channel-sync/1.0', 'Accept': 'application/json'}
    key = os.environ.get(env, '')
    if key:
        headers['Authorization'] = f'Bearer {key}'
    try:
        req = urllib.request.Request(base.rstrip('/') + '/models', headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except Exception:
        if os.path.exists(cache):  # 回退过期缓存
            return json.load(open(cache))
        raise
    items = []
    for m in data.get('data', []):
        mid = m['id']
        if not _is_free(mid, m.get('pricing')):
            continue
        # 最近一年内更新（created；无时间数据的剔除——如 kilo-auto/free 聚合入口）
        if not _recent(m.get('created', 0)):
            continue
        # 上下文：context_length 顶层或 top_provider 内；无数据保留
        ctx = m.get('context_length') or (m.get('top_provider') or {}).get('context_length')
        if not _context_ok(ctx):
            continue
        items.append({'id': mid, 'name': _pretty_name(mid)})
    with open(cache, 'w') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    return items


if __name__ == '__main__':
    import sys
    for ch in sys.argv[1:] or list(BASE):
        try:
            items = fetch_free_models(ch)
            print(f'{ch}: 免费模型 {len(items)} 个')
            for i in items:
                print('  -', i['id'])
        except Exception as e:
            print(f'{ch}: 提取失败 {e}')
