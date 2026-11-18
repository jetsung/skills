#!/usr/bin/env python3
"""模型清单获取与可用性实测（查询阶段工具，不写任何配置）。

用法:
    python3 model_probe.py list <渠道名> [--pi]
    python3 model_probe.py test <渠道名> [--pi] [模型id ...]
    python3 model_probe.py list --base-url <url> --api-key <key|ENV名>
    python3 model_probe.py test --base-url <url> --api-key <key|ENV名> 模型id ...

渠道配置来源（默认读 pi ~/.pi/agent/models.json 的 providers.{渠道}）:
    baseUrl + apiKey（pi 的 !echo -n "$VAR" / $VAR / 明文均自动解析为实值）。
    --base-url/--api-key 可覆盖；--api-key 传 ENV 变量名时取其实值，否则视为明文。

list 子命令: GET {baseUrl}/models，完整列出模型 id / created / 模态 / 上下文 /
    定价，并标注 free 判定（free 标签或 pricing prompt+completion 均为 0）。
    剔除纯图像/视频/音频输出、id 含 ocr 以及 tts/rerank/embedding/asr/whisper
    等非对话模型（/models 缺模态字段时按 id 兜底）。
    渠道为 nvidia / amd / jiutian 时再套用系列白名单 + 9 个月时间窗
    （无 created 的保留；SKIP_SERIES_FILTER=1 / SKIP_TIME_FILTER=1 可跳过）。

test 子命令: 逐个 POST {baseUrl}/chat/completions（max_tokens=8，先 curl 后 urllib）:
    - HTTP 200 且有 choices（content 或 reasoning 有值）→ 可用
    - HTTP 429（rate limit / inference exceeds tpm/rpm limit）→ 可用（临时限流）
    - HTTP 404 model is not found 且 /models 列表存在该 id → 生图模型（不入 pi/omp，
      无需二次探测 images 端点）
    - 其余（401/403 鉴权或套餐限制、404 且 /models 无、5xx、连接失败）→ 不可用
    默认测试 /models 实时列表全部模型；给了模型 id 参数则只测这些（id 不必在 /models 中）。
"""
import json, os, re, sys, time
import channel_check as cc
import pi_cache

PI_PATH = os.path.expanduser('~/.pi/agent/models.json')


def resolve_channel(name):
    """从 pi 配置读渠道 baseUrl 与 apiKey 实值。"""
    cfg = json.load(open(PI_PATH))
    pdata = cfg.get('providers', {}).get(name)
    if not pdata:
        raise SystemExit(f'pi 配置无渠道 {name}，现有渠道: '
                         + ', '.join(cfg.get('providers', {})))
    return pdata.get('baseUrl', ''), cc.pi_key_val(pdata.get('apiKey', ''))


def resolve_key(arg):
    """--api-key 参数：ENV 变量名（全大写下划线）取实值，否则视为明文。"""
    if re.fullmatch(r'[A-Z0-9_]+', arg) and os.environ.get(arg):
        return os.environ[arg]
    return arg


def fmt_ts(created):
    if not created:
        return '未知'
    return time.strftime('%Y-%m-%d %H:%M', time.localtime(created))


def is_zero_price(p):
    v = str(p).strip()
    try:
        return float(v) == 0
    except ValueError:
        return False


def fetch_models(base_url, api_key, timeout):
    """GET /models 返回 (原始 data 数组|None, 失败原因)。"""
    url = base_url.rstrip('/') + '/models'
    code, body, cerr = cc._curl_get(url, api_key, timeout)
    if not cerr:
        if code != 200:
            return None, f'HTTP {code}: {body[:150]}'
    else:
        try:  # urllib 兜底
            import urllib.request
            req = urllib.request.Request(url, headers={
                'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode('utf-8', 'replace')
        except Exception as e:
            return None, f'请求失败: {e}'
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None, '响应非 JSON'
    arr = data.get('data') if isinstance(data, dict) else None
    if not isinstance(arr, list):
        return None, '响应无 data 数组（/models 不提供列表）'
    return arr, ''


def classify(m):
    """提取展示字段与判定：free 标签 / 价格 0 / 生图等多模态信息。"""
    mid = m.get('id', '')
    pricing = m.get('pricing') or {}
    p_in = pricing.get('prompt')
    p_out = pricing.get('completion')
    free_tag = any(t in mid for t in (':free', '-free', '/free'))
    zero = (p_in is not None and is_zero_price(p_in)
            and is_zero_price(p_out or '0'))
    arch = m.get('architecture') or {}
    inp = m.get('input_modalities') or arch.get('input_modalities') or m.get('input') or []
    outp = m.get('output_modalities') or arch.get('output_modalities') or m.get('output') or []
    ctx = m.get('context_length') or m.get('contextWindow') or ''
    return {
        'id': mid, 'created': m.get('created', 0), 'name': m.get('name', mid),
        'free_tag': free_tag, 'zero': zero,
        'in': [str(x).lower() for x in inp], 'out': [str(x).lower() for x in outp],
        'ctx': ctx,
        'pricing': p_in if p_in is not None else '',
        'max_out': m.get('max_output_length', ''),
        'quant': m.get('quantization', ''),
    }


def is_multimodal_output(c):
    """输出不含 text → 图/视频/音频/OCR 类，不入清单。"""
    return bool(c['out']) and 'text' not in c['out']


NON_CHAT_HINTS = ('tts', 'rerank', 'embed', 'asr', 'whisper')


def is_non_chat(c):
    """id 命中 tts/rerank/embedding/asr/whisper → 非对话模型（/models 无模态字段时兜底）。"""
    mid = c['id'].lower()
    return any(h in mid for h in NON_CHAT_HINTS) or 'ocr' in mid


def is_classifier_output(c):
    """输出含 decision → classifier（决策模型）。上游这类条目的 context_length 常为 0、
    输出不含 text，但模型本身可用，不能按多模态/非对话剔除。"""
    return 'decision' in c['out']


def is_excluded_output(c):
    """不入对话模型清单：多模态输出（图/视频/音频）或非对话模型。
    classifier（decision 输出）例外，单独保留。"""
    if is_classifier_output(c):
        return False
    return is_multimodal_output(c) or is_non_chat(c)


def channel_rules(pname, cs):
    """按渠道约束过滤 classify 结果（与 pi_cache.filter_models 同步）：
    系列白名单（SKIP_SERIES_FILTER=1 跳过）+ 9 个月时间窗（SKIP_TIME_FILTER=1 跳过）。
    classifier（decision 输出）豁免这两条规则。返回 (保留列表, 剔除列表[{id, reason}])。
    非受限渠道原样返回。"""
    dropped = []
    if not pname:
        return cs, dropped
    key = pname.lower()

    def filtered(pred):
        """剔除「非 classifier 且不满足 pred」的条目，pred 为保留条件。"""
        nonlocal cs
        out = [c for c in cs if not is_classifier_output(c) and not pred(c)]
        if out:
            drop_ids = {c['id'] for c in out}
            cs = [c for c in cs if c['id'] not in drop_ids]
        return out

    if key in pi_cache.SERIES_CHANNELS and os.environ.get('SKIP_SERIES_FILTER') != '1':
        out = filtered(lambda c: pi_cache.series_allowed(c['id']))
        dropped += [{'id': c['id'], 'reason': '系列不在白名单'} for c in out]
    if key in pi_cache.TIME_FILTER_CHANNELS and os.environ.get('SKIP_TIME_FILTER') != '1':
        out = filtered(lambda c: pi_cache.created_recent(c['created']))
        dropped += [{'id': c['id'], 'reason': f'发布时间早于 {pi_cache.RECENT_MONTHS} 个月'}
                    for c in out]
    return cs, dropped


def cmd_list(base_url, api_key, names, timeout, pname=None):
    models, err = fetch_models(base_url, api_key, timeout)
    if models is None:
        print(f'获取模型列表失败: {err}')
        raise SystemExit(2)
    cs = sorted((classify(m) for m in models if isinstance(m, dict) and m.get('id')),
                key=lambda c: (c['created'], c['id']), reverse=True)
    excluded = [c for c in cs if is_excluded_output(c)]
    cs = [c for c in cs if not is_excluded_output(c)]
    cs, rule_dropped = channel_rules(pname, cs)
    active = []
    key = (pname or '').lower()
    if key in pi_cache.SERIES_CHANNELS and os.environ.get('SKIP_SERIES_FILTER') != '1':
        active.append('系列白名单')
    if key in pi_cache.TIME_FILTER_CHANNELS and os.environ.get('SKIP_TIME_FILTER') != '1':
        active.append(f'{pi_cache.RECENT_MONTHS} 个月时间窗')
    rule_note = (f"，已套用 {' + '.join(active)}（SKIP_SERIES_FILTER=1 / "
                 'SKIP_TIME_FILTER=1 可跳过）') if active else ''
    print(f'# {names} /models 清单（共 {len(models)} 个，剔除图/视频/音频/OCR/非对话 {len(excluded)} 个'
          f'，规则剔除 {len(rule_dropped)} 个{rule_note}）\n')
    for c in cs:
        src = 'free标签' if c['free_tag'] and not c['zero'] else \
              '价格0' if c['zero'] and not c['free_tag'] else \
              '价格0+free标签' if c['zero'] and c['free_tag'] else '付费'
        kind = 'classifier' if is_classifier_output(c) else 'chat'
        print(f"{fmt_ts(c['created'])} | {c['id']} | {kind} | {src} | in={c['in'] or '?'} "
              f"out={c['out'] or '?'} | ctx={c['ctx'] or '?'} maxOut={c['max_out'] or '?'} "
              f"| price={c['pricing']} | {c['quant'] or '-'}")
    if excluded:
        print(f"\n# 已剔除（多模态输出/OCR/非对话，不入同步）: {', '.join(c['id'] for c in excluded)}")
    clf = [c['id'] for c in cs if is_classifier_output(c)]
    if clf:
        print(f"\n# classifier（决策模型，仅 pi 的 codemode models.classify 可用，不入其它平台）: "
              f"{', '.join(clf)}")
    if rule_dropped:
        print('# 已剔除（渠道规则）: '
              + '、'.join(f"{d['id']}（{d['reason']}）" for d in rule_dropped))


def probe_chat_one(base_url, api_key, mid, timeout):
    """单模型 chat 实测，返回 (状态, 说明)。状态 ∈ 可用/限流可用/生图模型/不可用。"""
    url = base_url.rstrip('/') + '/chat/completions'
    body = json.dumps({'model': mid,
                       'messages': [{'role': 'user', 'content': 'ping'}],
                       'max_tokens': 8, 'stream': False})
    code, resp, cerr = cc._curl_post(url, api_key, body, timeout)
    if cerr:
        code, resp = 0, ''
        try:  # urllib 兜底
            import urllib.request
            req = urllib.request.Request(url, data=body.encode(), headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                code, resp = r.status, r.read().decode('utf-8', 'replace')
        except Exception as e:
            return '不可用', f'连接失败: {e}'
        return judge(code, resp, mid)
    return judge(code, resp, mid)


def judge(code, resp, mid):
    if code == 200:
        try:
            d = json.loads(resp)
        except json.JSONDecodeError:
            return '不可用', f'HTTP 200 但响应非 JSON: {resp[:120]}'
        ch = (d.get('choices') or [{}])[0]
        msg = ch.get('message') or {}
        if msg.get('content') or msg.get('reasoning'):
            return '可用', 'HTTP 200（content/reasoning 有值）'
        if d.get('choices'):
            return '可用', 'HTTP 200（有 choices）'
        return '不可用', f'HTTP 200 但无 choices: {resp[:120]}'
    if code == 429:
        return '可用', 'HTTP 429 限流（临时限额，模型存在）'
    detail = ''
    try:
        e = json.loads(resp).get('error')
        detail = (e.get('message', '') if isinstance(e, dict) else str(e)) or resp[:120]
    except Exception:
        detail = resp[:120]
    return 'FAIL', f'HTTP {code}: {detail[:200]}'


def cmd_test(base_url, api_key, ids, timeout, quiet_limit=False, pname=None):
    models, _ = fetch_models(base_url, api_key, timeout)
    api_ids = {m.get('id') for m in (models or []) if isinstance(m, dict)}
    clf_ids = {c['id'] for c in (classify(m) for m in (models or [])
                                if isinstance(m, dict) and m.get('id'))
               if is_classifier_output(c)}
    targets = list(ids)
    if not targets:
        cs = [classify(m) for m in (models or []) if isinstance(m, dict) and m.get('id')]
        cs = [c for c in cs if not is_excluded_output(c)]
        targets = sorted(c['id'] for c in channel_rules(pname, cs)[0]
                         if not is_classifier_output(c))
    skipped = [m for m in targets if m in clf_ids]
    targets = [m for m in targets if m not in clf_ids]
    if skipped:
        print(f"# 跳过 classifier（决策模型，不适用 chat 实测）: {', '.join(skipped)}\n")
    if not targets:
        print('无可测模型（/models 未返回列表且未显式指定 id）')
        raise SystemExit(2)
    print(f'# chat 实测 {len(targets)} 个模型\n')
    results = {}
    for mid in targets:
        st, note = probe_chat_one(base_url, api_key, mid, timeout)
        if st == 'FAIL':
            if mid in api_ids and re.search(r'not[_ ]found|model is not found',
                                            note, re.I):
                st, note = '生图模型', 'HTTP 404 model not found，但 /models 存在 → 走生图接口，不入 pi/omp'
            elif re.search(r'region', note, re.I):
                st, note = '不可用', '地区限制 — ' + note
            elif re.search(r'available in the current token plan|403', note, re.I):
                st, note = '不可用', '套餐不提供该模型 — ' + note
        results[mid] = (st, note)
        print(f'  {mid}: {st} — {note}')
    ok = [m for m, (s, _) in results.items() if s == '可用']
    img = [m for m, (s, _) in results.items() if s == '生图模型']
    bad = [m for m, (s, _) in results.items() if s == '不可用']
    print(f'\n# 小结: 可用 {len(ok)} | 生图模型 {len(img)}（不入 pi/omp）| 不可用 {len(bad)}')
    if ok:
        print('  可用: ' + ', '.join(ok))
    if img:
        print('  生图: ' + ', '.join(img))
    if bad:
        print('  不可用: ' + ', '.join(bad))


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ('list', 'test'):
        print(__doc__.strip().splitlines()[0])
        print('用法: python3 model_probe.py <list|test> <渠道名|--base-url ... --api-key ...> [模型id ...]')
        raise SystemExit(1)
    cmd = args.pop(0)
    timeout, base_url, api_key, ids, name = 30, None, None, [], None
    rest = []
    i = 0
    while i < len(args):
        if args[i] == '--pi':
            i += 1
        elif args[i] == '--base-url':
            base_url = args[i + 1]; i += 2
        elif args[i] == '--api-key':
            api_key = resolve_key(args[i + 1]); i += 2
        elif args[i] == '--timeout':
            timeout = int(args[i + 1]); i += 2
        else:
            rest.append(args[i]); i += 1
    if rest and not rest[0].startswith('/') and not base_url:
        name, ids = rest[0], rest[1:]
        base_url, api_key = resolve_channel(name)
        if not api_key:
            print(f'渠道 {name} 的 apiKey 无法解析（检查环境变量是否已设置）')
            raise SystemExit(2)
    elif not base_url:
        print('缺少渠道名或 --base-url/--api-key')
        raise SystemExit(1)
    names = f'{name}（{base_url}）' if name else base_url
    if cmd == 'list':
        cmd_list(base_url, api_key, names, timeout, pname=name)
    else:
        cmd_test(base_url, api_key, ids, timeout, pname=name)


if __name__ == '__main__':
    main()
