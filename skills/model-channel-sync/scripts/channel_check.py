#!/usr/bin/env python3
"""渠道可用性检查层：同步前验证 pi 渠道的 apiKey/baseUrl 是否真正可用。

判定方式：调 OpenAI 兼容 `GET {baseUrl}/models`，HTTP 200 且返回 data 数组
（允许为空列表——部分网关不实现 /models，此时 HTTP 200 即视为密钥有效）。
- 提取不到模型（HTTP 401/403 鉴权失败、连接失败、非 JSON 响应）→ 渠道不可用，
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


def check(channel, base_url, api_key, timeout=15):
    """验证渠道可用性，返回 {ok: bool, reason: str}。结果缓存 1 小时（成功/失败分开缓存）。"""
    if os.environ.get('CHECK_OFFLINE') == '1':
        return {'ok': True, 'reason': 'offline-skip'}
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = os.path.join(CACHE_DIR, f'check-{channel}.json')
    if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < CACHE_TTL:
        try:
            return json.load(open(cache))
        except (json.JSONDecodeError, OSError):
            pass  # 缓存损坏则重新检查
    result = _probe(base_url, api_key, timeout)
    with open(cache, 'w') as f:
        json.dump(result, f, ensure_ascii=False)
    return result


def ok(channel, base_url, api_key, timeout=15):
    """渠道可用返回 True；不可用（提取不到模型/鉴权失败/连接失败）返回 False。"""
    return check(channel, base_url, api_key, timeout)['ok']


def reason(channel, base_url, api_key, timeout=15):
    """返回不可用原因；可用时返回空字符串。"""
    r = check(channel, base_url, api_key, timeout)
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
    r = check(pname, pdata.get('baseUrl') or '', pi_key_val(pdata.get('apiKey')))
    return '' if r['ok'] else r['reason']


def _probe(base_url, api_key, timeout):
    """实际请求 GET {baseUrl}/models 判定可用性。"""
    if not base_url:
        return {'ok': False, 'reason': 'baseUrl 为空'}
    url = base_url.rstrip('/') + '/models'
    headers = {'User-Agent': 'model-channel-sync/1.0', 'Accept': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
        data = json.loads(body)
        # HTTP 200：有 data 数组取实时模型 id 列表；无 /models 端点但返回合法 JSON 也视为密钥有效
        ids = []
        if isinstance(data, dict) and isinstance(data.get('data'), list):
            ids = [m['id'] for m in data['data'] if isinstance(m, dict) and m.get('id')]
        return {'ok': True, 'reason': f'{len(ids)} 个模型' if ids else '端点可达（无模型列表）',
                'model_ids': ids}
    except urllib.error.HTTPError as e:
        # 405 = 端点存在但不支持 GET（如仅 POST 的网关）→ 渠道本身可达，视为可用
        if e.code == 405:
            return {'ok': True, 'reason': '端点可达（不支持 GET /models）'}
        detail = ''
        try:
            detail = e.read().decode('utf-8', 'replace')[:120]
        except Exception:
            pass
        return {'ok': False, 'reason': f'HTTP {e.code}（鉴权失败或端点错误）{(": " + detail) if detail else ""}'}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {'ok': False, 'reason': f'连接失败: {e}'}
    except json.JSONDecodeError:
        return {'ok': False, 'reason': '响应非 JSON（端点不兼容）'}


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
