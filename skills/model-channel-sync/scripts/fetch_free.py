#!/usr/bin/env python3
"""上游免费模型提取（kilo / opencode / openrouter / anyapi 渠道）。

提供 fetch_free_models(channel) -> [{id, name, contextWindow?, maxTokens?}]：
- 免费判定：id 含 :free/-free//free 标签，或 pricing.prompt/completion 均为 0（含临时免费）
- 剔除图像/视频/音频模型（EXCLUDE 关键词）
- **最近一年内更新**：created/release 时间早于一年前的剔除（无时间数据的模型保留，
  如 kilo 的 kilo-auto/free 是聚合入口非真实模型则按 created=0 剔除——见 _recent 规则）。
  anyapi 渠道的 created 为静态占位值（所有模型均为同一旧时间戳），跳过 recency 检查。
- **上下文限制**：context 若存在则必须 >100K（无 context 数据的模型保留）
- 结果缓存 ~/.cache/model-channel-sync/free-{channel}.json（1 小时）；
  上游请求失败时回退上次缓存，无缓存则抛异常（由调用方决定回退 pi models）
- **限制同步**：API 返回的上下文/最大输出限制随条目一起返回（`contextWindow`/`maxTokens`，
  仅在有数据时携带）：context 取 `context_length`（顶层或 `top_provider` 内）或
  `max_input_tokens`（anyapi）；max_output 取 `max_completion_tokens`/`max_output_tokens`
  （顶层、`top_provider` 或 `architecture.output_length`）；旧缓存缺字段时 .get 为 None，
  调用方按参考值回退
"""
import json, os, re, time, urllib.request
from datetime import date, datetime, timedelta

BASE = {
    'kilo':       ('https://api.kilo.ai/api/gateway/v1', 'KILO_API_KEY'),
    'opencode':   ('https://opencode.ai/zen/v1', 'OPENCODE_API_KEY'),
    'openrouter': ('https://openrouter.ai/api/v1', 'OPENROUTER_API_KEY'),
    'anyapi':     ('https://api.anyapi.ai/v1', 'ANYAPI_API_KEY'),
}
# 剔除的模型关键词（图像/视频/音频类，不适合编程对话）
EXCLUDE = ('lyria', 'image', 'video', 'whisper', 'tts')
# 上下文门槛：context 存在时必须大于该值
MIN_CONTEXT = 100_000
# 更新时间门槧：最近一年
RECENT_DAYS = 365
# 渠道级配置：跳过 recency 检查（created 为静态占位值，不反映真实更新时间）
SKIP_RECENT = ('anyapi',)
CACHE_DIR = os.path.expanduser('~/.cache/model-channel-sync')
CACHE_TTL = 3600


def _is_free(mid, pricing):
    """免费判定：free 标签 或 价格（prompt/completion）均为 0

    注意：当渠道 API 不提供 pricing 字段时，price=0 路径不可用，
    仅凭 free 标签判断（如 anyapi）。缺字段不当作 0。"""
    low = mid.lower()
    if any(x in low for x in EXCLUDE):
        return False
    if ':free' in low or '-free' in low or '/free' in low:
        return True
    p = pricing or {}

    def zero(x):
        # None/缺字段不视为 0，避免无定价数据的模型被误判为免费
        if x is None:
            return False
        try:
            return float(x) == 0
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


def _limits(m):
    """提取 API 返回的限制：(contextWindow, maxTokens)；无数据返回 None"""
    tp = m.get('top_provider') or {}
    arch = m.get('architecture') or {}
    ctx = (m.get('context_length') or tp.get('context_length')
           or m.get('max_input_tokens'))
    mout = (m.get('max_completion_tokens') or m.get('max_output_tokens')
            or tp.get('max_completion_tokens') or tp.get('max_output_tokens')
            or arch.get('output_length'))
    return (ctx or None), (mout or None)


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
    """返回渠道上游的免费模型列表 [{id, name, contextWindow?, maxTokens?}]，带 1 小时缓存与失败回退"""
    if channel not in BASE:
        raise ValueError(f'未知渠道: {channel}')
    base, env = BASE[channel]
    skip_recent = channel in SKIP_RECENT
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
        # 近期更新检查：anyapi 的 created 为静态占位值，跳过
        if not skip_recent and not _recent(m.get('created', 0)):
            continue
        # 上下文限制
        ctx, mout = _limits(m)
        if not _context_ok(ctx):
            continue
        item = {'id': mid, 'name': _pretty_name(mid)}
        if ctx is not None:
            item['contextWindow'] = ctx
        if mout is not None:
            item['maxTokens'] = mout
        items.append(item)
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