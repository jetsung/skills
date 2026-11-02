#!/usr/bin/env python3
"""渠道可用性检查层：同步前验证 pi 渠道的 apiKey/baseUrl 是否真正可用。

判定方式：两段式实测——
① 调 OpenAI 兼容 `GET {baseUrl}/models` 探测端点可达性并拿实时模型列表；
② 用候选模型调 `POST {baseUrl}/chat/completions` 发最小真实请求（max_tokens=8），
   验证鉴权与真实推理能力。仅 /models 返回 200 不足为凭（部分网关 /models 不鉴权、
   无密钥也返回模型列表），必须 chat 测试通过才判可用。
- chat 测试 HTTP 200 且有 choices → 可用；HTTP 429 限流 → 可用（临时限额，模型存在）
- chat 测试 401/403（鉴权失败）、候选模型全部 404/5xx、连接失败 → 渠道不可用，
  同步脚本应整条跳过该渠道并在报告中注明
- 结果缓存 ~/.cache/model-channel-sync/check-{渠道}.json（TTL 1 小时），
  成功/失败分开缓存（缓存 {ok: bool, reason: str}），避免每次同步都发请求
- 无网络环境下可用 CHECK_OFFLINE=1 跳过检查（视为可用，保持原行为）

用法（在同步脚本中）:
    import channel_check
    if not channel_check.ok(pname, base_url, api_key):
        out.append(f'{pname}: 跳过（{channel_check.reason(pname, base_url, api_key)}）')
        continue
"""
import json, os, sys, time, urllib.request, urllib.error

sys.dont_write_bytecode = True  # 本模块被导入，不生成 __pycache__

CACHE_DIR = os.path.expanduser('~/.cache/model-channel-sync')
CACHE_TTL = 3600  # 1 小时


def check(channel, base_url, api_key, timeout=15, models=None):
    """验证渠道可用性，返回 {ok: bool, reason: str}。结果缓存 1 小时（成功/失败分开缓存）。

    models: 候选模型 id 列表，用于 chat/completions 实测（默认取 /models 返回的前 3 个，
    或渠道自带的模型 id；两者都无则退化为仅端点探测）。仅端点探测（无候选模型）
    时只保证可达，不证明鉴权/推理能力——此时 reason 会注明"未做 chat 实测"。"""
    if os.environ.get('CHECK_OFFLINE') == '1':
        return {'ok': True, 'reason': 'offline-skip'}
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = os.path.join(CACHE_DIR, f'check-{channel}.json')
    if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < CACHE_TTL:
        try:
            return json.load(open(cache))
        except (json.JSONDecodeError, OSError):
            pass  # 缓存损坏则重新检查
    result = _probe(base_url, api_key, timeout, models)
    with open(cache, 'w') as f:
        json.dump(result, f, ensure_ascii=False)
    return result


def ok(channel, base_url, api_key, timeout=15, models=None):
    """渠道可用返回 True；不可用（提取不到模型/鉴权失败/连接失败）返回 False。"""
    return check(channel, base_url, api_key, timeout, models)['ok']


def reason(channel, base_url, api_key, timeout=15, models=None):
    """返回不可用原因；可用时返回空字符串。"""
    r = check(channel, base_url, api_key, timeout, models)
    return '' if r['ok'] else r['reason']



def pi_key_val(apikey_field):
    """pi 的 `!echo -n "$VAR"` 形式 → 环境变量实值；其它形式返回 None。"""
    import re
    m = re.match(r'!echo -n "\$([A-Z0-9_]+)"', apikey_field or '')
    return os.environ.get(m.group(1)) if m else None


def pi_key_val(apikey_field):
    """解析 pi 的 apiKey 字段为实值：!echo -n "$VAR" / "$VAR" / "${VAR}" 取环境变量，
    其它（明文）原样返回；取不到环境变量返回 None。"""
    import re
    s = apikey_field or ''
    m = re.match(r'!echo -n "\$([A-Z0-9_]+)"', s) or re.match(r'^\$\{?([A-Z0-9_]+)\}?$', s)
    if m:
        return os.environ.get(m.group(1))
    return s or None


def skip_reason(pname, pdata):
    """同步脚本统一入口：渠道不可用返回原因字符串，可用返回 ''。"""
    models = [m['id'] for m in pdata.get('models', []) if isinstance(m, dict) and m.get('id')]
    r = check(pname, pdata.get('baseUrl') or '', pi_key_val(pdata.get('apiKey')), models=models)
    return '' if r['ok'] else r['reason']


def _probe(base_url, api_key, timeout, models=None):
    """两段式实测：① GET {baseUrl}/models 探测端点并取实时模型 id；② 用候选模型
    POST {baseUrl}/chat/completions 发最小真实请求验证鉴权与推理能力。
    仅 ① 通过不足为凭（部分网关 /models 不鉴权、无密钥也返回模型列表），
    必须 chat 实测通过（HTTP 200 有 choices，或 429 限流）才判可用。"""
    if not base_url:
        return {'ok': False, 'reason': 'baseUrl 为空'}
    ids, models_note = _probe_models(base_url, api_key, timeout)
    if ids is None:
        return {'ok': False, 'reason': models_note}  # /models 端点级失败
    # 候选模型：显式传入 > /models 实时列表 > 渠道自带列表
    candidates = list(models or []) or ids[:3]
    if not candidates:
        return {'ok': True, 'reason': '端点可达（无候选模型，未做 chat 实测）', 'model_ids': ids}
    chat = _probe_chat(base_url, api_key, candidates, timeout)
    if not chat['ok']:
        return {'ok': False, 'reason': chat['reason'], 'model_ids': ids}
    return {'ok': True, 'reason': chat['reason'], 'model_ids': ids, 'chat_model': chat.get('chat_model')}

def _curl_get(url, api_key, timeout):
    """curl 后备请求（GET）：urllib TLS 握手失败（如 OpenSSL 版本与服务器不兼容）
    时回退 curl。返回 (HTTP 码, 响应文本, None)；连接失败返回 (0, '', 原因)。"""
    import subprocess
    cmd = ['curl', '-s', '-m', str(timeout), '-w', '\n%{http_code}']
    if api_key:
        cmd += ['-H', f'Authorization: Bearer {api_key}']
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
    except (subprocess.TimeoutExpired, OSError) as e:
        return 0, '', f'curl 失败: {e}'
    out = r.stdout
    body, _, code = out.rpartition('\n')
    try:
        return int(code), body, ''
    except ValueError:
        return 0, body, f'curl 响应无 HTTP 码: {out[:80]}'


def _curl_post(url, api_key, body, timeout):
    """curl 后备请求（POST）。返回 (HTTP 码, 响应文本, 错误原因)。"""
    import subprocess
    cmd = ['curl', '-s', '-m', str(timeout), '-w', '\n%{http_code}',
           '-X', 'POST', '-H', 'Content-Type: application/json']
    if api_key:
        cmd += ['-H', f'Authorization: Bearer {api_key}']
    cmd += ['-d', body, url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
    except (subprocess.TimeoutExpired, OSError) as e:
        return 0, '', f'curl 失败: {e}'
    out = r.stdout
    resp, _, code = out.rpartition('\n')
    try:
        return int(code), resp, ''
    except ValueError:
        return 0, resp, f'curl 响应无 HTTP 码: {out[:80]}'


def _parse_ids(body):
    """从 /models 响应解析模型 id 列表。"""
    try:
        data = json.loads(body)
        if isinstance(data, dict) and isinstance(data.get('data'), list):
            return [m['id'] for m in data['data'] if isinstance(m, dict) and m.get('id')]
        return []
    except (json.JSONDecodeError, TypeError):
        return None


def _probe_models(base_url, api_key, timeout):
    """GET {baseUrl}/models。返回 (模型 id 列表, '' )；端点级失败返回 (None, 原因)。
    优先 curl（TLS 栈更通用，部分服务器对 urllib 握手挂起）；urllib 作为兜底。
    HTTP 405 / 无 data 数组但 HTTP 200 → 端点可达但无模型列表，返回 ([], '')。"""
    url = base_url.rstrip('/') + '/models'
    code, body, cerr = _curl_get(url, api_key, timeout)
    if not cerr:
        if code == 405:
            return [], ''
        if code == 429:
            return [], '429'
        if code == 200:
            ids = _parse_ids(body)
            return (ids if ids is not None else []), ''
        return None, f'HTTP {code}（鉴权失败或端点错误）{(": " + body[:120]) if body else ""}'
    # curl 不可用 → urllib 兜底
    headers = {'User-Agent': 'model-channel-sync/1.0', 'Accept': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
        ids = _parse_ids(body)
        return (ids if ids is not None else []), ''
    except urllib.error.HTTPError as e:
        if e.code == 405:
            return [], ''
        if e.code == 429:
            return [], '429'
        detail = ''
        try:
            detail = e.read().decode('utf-8', 'replace')[:120]
        except Exception:
            pass
        return None, f'HTTP {e.code}（鉴权失败或端点错误）{(": " + detail) if detail else ""}'
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, f'连接失败: {e}'
    except json.JSONDecodeError:
        return None, '响应非 JSON（端点不兼容）'


def _probe_chat(base_url, api_key, candidates, timeout):
    """POST {baseUrl}/chat/completions，逐个候选模型发最小请求，直到一个通过。
    返回 {ok: bool, reason: str, chat_model: str|None}。
    优先 curl（TLS 栈更通用）；urllib 作为兜底。
    HTTP 200 有 choices → 可用；HTTP 429 → 可用（限流，模型存在）；其余全部失败 → 不可用。"""
    url = base_url.rstrip('/') + '/chat/completions'
    errs = []
    for mid in candidates[:5]:  # 最多试 5 个候选
        body = json.dumps({'model': mid, 'messages': [{'role': 'user', 'content': 'ping'}],
                           'max_tokens': 8, 'stream': False})
        code, cbody, cerr = _curl_post(url, api_key, body, timeout)
        if cerr:
            errs.append(f'{mid}: 连接失败 {cerr}')
            continue
        if code == 429:
            return {'ok': True, 'reason': f'429 限流（可用，临时限额，{mid}）', 'chat_model': mid}
        if code == 200:
            try:
                resp = json.loads(cbody)
                if isinstance(resp, dict) and resp.get('choices'):
                    return {'ok': True, 'reason': f'chat 实测可用（{mid}）', 'chat_model': mid}
                errs.append(f'{mid}: chat 响应无 choices: {cbody[:120]}')
            except json.JSONDecodeError:
                errs.append(f'{mid}: 响应非 JSON')
        else:
            errs.append(f'{mid}: HTTP {code} {cbody[:120]}')
    return {'ok': False, 'reason': 'chat 实测全部失败: ' + ' | '.join(errs), 'chat_model': None}


if __name__ == '__main__':
    import sys
    # 命令行自检：python3 channel_check.py 渠道名 baseUrl apiKey ...
    args = sys.argv[1:]
    if not args:
        print('用法: python3 channel_check.py <渠道名> <baseUrl> <apiKey> [渠道名 baseUrl apiKey ...]')
        raise SystemExit(1)
    for i in range(0, len(args), 3):
        ch, bu, ak = args[i:i + 3]
        r = check(ch, bu, ak)
        print(f'{ch}: {"可用" if r["ok"] else "不可用"}（{r["reason"]}）')
