#!/usr/bin/env python3
"""pi → zcode 全量同步（合并式：保留 zcode 现有 + 补 pi 缺失 + 更新 apiKey）。

用法:
    python3 scripts/sync-pi-to-zcode.py

按需修改下方 PI_PATH / ZC_PATH / ALIAS。
规则：
- baseURL / kind（兼容模式）：**不更新已有值**，仅当目标缺失/为空时从 pi 补入
  （kind 由 pi 的 api 字段映射：openai-completions → openai-compatible，anthropic → anthropic）
- apiKey：解析 pi 的 !echo -n "$VAR" 读环境变量，写入明文 options.apiKey
- models：合并（保留 zcode 现有 + 补 pi 缺失），幂等
幂等可重复执行；自动备份（.bak-YYYYMMDD）并断言校验；密钥不回显。
"""
import json, re, os, shutil, datetime

PI_PATH = os.path.expanduser('~/.pi/agent/models.json')
ZC_PATH = os.path.expanduser('~/.zcode/v2/config.json')
ALIAS = {'cloudflare-workers-ai': 'CloudFlare AI'}  # 规范化后不匹配的渠道手动映射
KIND_MAP = {'openai-completions': 'openai-compatible', 'anthropic': 'anthropic'}


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


stamp = datetime.date.today().strftime('%Y%m%d')
shutil.copy(ZC_PATH, ZC_PATH + '.bak-' + stamp)
pi = json.load(open(PI_PATH))
zc = json.load(open(ZC_PATH))
zname2key = {norm(p['name']): k for k, p in zc['provider'].items() if 'name' in p}

out = []
for pname, pdata in pi['providers'].items():
    key = zname2key.get(norm(ALIAS.get(pname, pname)))
    if key is None:
        out.append(f'跳过 {pname}: zcode 无对应 provider')
        continue
    prov = zc['provider'][key]
    # 空值补充：仅当目标缺失/为空时从 pi 补入 baseURL / kind
    opts = prov.setdefault('options', {})
    if not opts.get('baseURL'):
        opts['baseURL'] = pdata.get('baseUrl', '')
        out.append(f'{pname}: baseURL 空值补充')
    if not prov.get('kind'):
        prov['kind'] = KIND_MAP.get(pdata.get('api', ''), 'openai-compatible')
        out.append(f'{pname}: kind 空值补充（{prov["kind"]}）')
    # 合并 models（幂等）
    existing = set(prov.get('models', {}))
    prios = [m.get('zcode', {}).get('priority', 0) for m in prov.get('models', {}).values()
             if isinstance(m, dict)]
    nxt = (max(prios) if prios else 99) + 1
    added = []
    for item in pdata.get('models', []):
        if item['id'] not in existing:
            prov['models'][item['id']] = {'name': item.get('name', item['id']),
                                          'zcode': {'modified': True, 'priority': nxt}}
            nxt += 1
            added.append(item['id'])
    # apiKey：env 解析（正则含数字）→ 明文写入
    m = re.match(r'!echo -n "\$([A-Z0-9_]+)"', pdata.get('apiKey', ''))
    if m and os.environ.get(m.group(1)):
        changed = opts.get('apiKey') != os.environ[m.group(1)]
        opts['apiKey'] = os.environ[m.group(1)]
        out.append(f'{pname}: apiKey {"更新" if changed else "一致"} 新增模型 {len(added)} 个 {added if added else ""}')
    else:
        out.append(f'{pname}: apiKey 跳过（env 未设置/非占位符） 新增模型 {len(added)} 个')

with open(ZC_PATH, 'w') as f:
    json.dump(zc, f, ensure_ascii=False, indent=2)
    f.write('\n')

bak = json.load(open(ZC_PATH + '.bak-' + stamp))
assert list(bak['provider'].keys()) == list(zc['provider'].keys()), 'provider 键序被改动'
for k in zc['provider']:
    b, c = bak['provider'][k], zc['provider'][k]
    bm, cm = b.get('models', {}), c.get('models', {})
    assert all(bm[kk] == cm[kk] for kk in bm if kk in cm), f'{k}: 现有模型条目被改动'
    # kind：已有值不可变，仅允许空→非空
    assert {kk: vv for kk, vv in b.items() if kk not in ('options', 'models', 'kind')} == \
           {kk: vv for kk, vv in c.items() if kk not in ('options', 'models', 'kind')}, f'{k}: 顶层字段被改动'
    if b.get('kind'):
        assert c.get('kind') == b['kind'], f'{k}: kind 被改动（已有值）'
    # options：apiKey 允许变；baseURL 已有值不可变，仅允许空→非空；其余全等
    bo, co = b.get('options', {}), c.get('options', {})
    for kk, vv in bo.items():
        if kk == 'apiKey':
            continue
        if kk == 'baseURL':
            assert co.get('baseURL') == vv or (not vv and co.get('baseURL')), f'{k}: baseURL 被改动（已有值）'
        else:
            assert co.get(kk) == vv, f'{k}: options.{kk} 被改动'
print('校验通过：仅 models 新增 / apiKey 更新 / 空值补充 baseURL+kind')
print('\n'.join(out))