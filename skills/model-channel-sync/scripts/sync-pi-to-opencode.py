#!/usr/bin/env python3
"""pi → opencode 同步（合并式：保留现有 + 补 pi 缺失模型）。

用法:
    python3 scripts/sync-pi-to-opencode.py

opencode 的 apiKey 为 {env:XXX} 占位符，保留不动；只同步 models
（对象 map，key = 模型 id，value = {id, name, family}，family 规则 = id 前缀或渠道名）。
pi 条目提供 contextWindow/maxTokens 限制时，新增条目写入 `limit.context/limit.output`，
现有条目不一致即同步更新（来源为权威值）。
幂等可重复执行；自动备份（.bak-YYYYMMDD）；断言校验只允许 models 新增与限制字段同步；密钥不回显。
"""
import json, re, os, shutil, datetime

PI_PATH = os.path.expanduser('~/.pi/agent/models.json')
OC_PATH = os.path.expanduser('~/.config/opencode/opencode.json')
ALIAS = {'cloudflare-workers-ai': 'cloudflare-workers-ai'}  # 与 pi 同名，保留可扩展


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


stamp = datetime.date.today().strftime('%Y%m%d')
shutil.copy(OC_PATH, OC_PATH + '.bak-' + stamp)
pi = json.load(open(PI_PATH))
oc = json.load(open(OC_PATH))
providers = oc['provider']

out = []
srclim_by_key = {}  # provider key → {模型 id: {context?, output?}}（限制同步的断言放行依据）
for pname, pdata in pi['providers'].items():
    if pname in providers:
        key = pname
    elif ALIAS.get(pname) in providers:
        key = ALIAS[pname]
    else:
        key = {norm(k): k for k in providers}.get(norm(pname))
    if key is None:
        out.append(f'跳过 {pname}: opencode 无对应 provider')
        continue
    prov = providers[key]
    opts = prov.setdefault('options', {})
    if not opts.get('baseURL'):  # 规则：不更新已有值，仅空值补充（env 占位符风格）
        m = re.match(r'\{env:([A-Z0-9_]+)\}', opts.get('apiKey', ''))
        env_base = (m.group(1)[:-8] + '_BASE_URL') if m and m.group(1).endswith('_API_KEY') else 'BASE_URL'
        opts['baseURL'] = '{env:' + env_base + '}'
        out.append(f'{pname}: baseURL 空值补充（{opts["baseURL"]}）')
    models = prov.setdefault('models', {})
    existing = set(models)
    added = []
    limupd = []
    srclim = {}
    for item in pdata.get('models', []):
        mid = item['id']
        lim = {}
        if item.get('contextWindow'):
            lim['context'] = item['contextWindow']
        if item.get('maxTokens'):
            lim['output'] = item['maxTokens']
        if lim:
            srclim[mid] = lim
        if mid not in existing:
            family = mid.split('/')[0] if '/' in mid else key
            entry = {'id': mid, 'name': item.get('name', mid), 'family': family}
            if lim:
                entry['limit'] = lim
            models[mid] = entry
            added.append(mid)
        elif lim:
            tl = models[mid].setdefault('limit', {})
            for lk, lv in lim.items():
                if tl.get(lk) != lv:
                    limupd.append(f'{mid}.limit.{lk} {tl.get(lk)}→{lv}')
                    tl[lk] = lv
    srclim_by_key[key] = srclim
    if limupd:
        out.append(f'{pname}: 限制同步 {len(limupd)} 项 {limupd}')
    out.append(f'{pname}: 新增模型 {len(added)} 个 {added if added else ""}')

with open(OC_PATH, 'w') as f:
    json.dump(oc, f, ensure_ascii=False, indent=2)
    f.write('\n')

bak = json.load(open(OC_PATH + '.bak-' + stamp))
assert list(bak['provider'].keys()) == list(providers.keys()), 'provider 键序被改动'
for k in providers:
    b, c = bak['provider'][k], providers[k]
    bm, cm = b.get('models', {}), c.get('models', {})
    allow_all = srclim_by_key.get(k, {})
    for mk, mv in bm.items():
        if mk not in cm:
            continue
        assert {kk: vv for kk, vv in mv.items() if kk != 'limit'} == \
               {kk: vv for kk, vv in cm[mk].items() if kk != 'limit'}, f'{k}: 现有模型条目 {mk} 被改动'
        allow = allow_all.get(mk, {})
        for lk, lv in ((mv.get('limit') or {}) if isinstance(mv, dict) else {}).items():
            if (cm[mk].get('limit') or {}).get(lk) != lv:
                assert allow.get(lk) == (cm[mk].get('limit') or {}).get(lk), \
                    f'{k}: 现有模型条目 {mk} 的 limit.{lk} 被改动（无来源依据）'
    assert {kk: vv for kk, vv in b.items() if kk not in ('models', 'options')} == \
           {kk: vv for kk, vv in c.items() if kk not in ('models', 'options')}, f'{k}: 非 models/options 字段被改动'
    bo, co = b.get('options', {}), c.get('options', {})
    for kk, vv in bo.items():
        if kk == 'baseURL':
            assert co.get('baseURL') == vv or (not vv and co.get('baseURL')), f'{k}: baseURL 被改动（已有值）'
        else:
            assert co.get(kk) == vv, f'{k}: options.{kk} 被改动'
print('校验通过：仅 models 新增 / 限制字段同步')
print('\n'.join(out))