#!/usr/bin/env python3
"""pi → dsh 同步（合并式：保留现有 + 补 pi 缺失模型）。

用法:
    python3 scripts/sync-pi-to-dsh.py

dsh 的 apiKeyEnv 为环境变量名，保留不动；只同步 models
（YAML 列表，元素仅 {id}，遵循 dsh 原有格式）。幂等可重复执行；
自动备份（.bak-YYYYMMDD）；断言校验只允许 models 新增；密钥不回显。
"""
import json, re, os, shutil, datetime
import yaml

PI_PATH = os.path.expanduser('~/.pi/agent/models.json')
DSH_PATH = os.path.expanduser('~/.dsh/settings.yaml')
ALIAS = {'cloudflare-workers-ai': 'cloudflare-workers-ai'}  # dsh 有同名渠道，保留可扩展


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


stamp = datetime.date.today().strftime('%Y%m%d')
shutil.copy(DSH_PATH, DSH_PATH + '.bak-' + stamp)
pi = json.load(open(PI_PATH))
dsh = yaml.safe_load(open(DSH_PATH))
providers = dsh['llm-pi-ai']['providers']

out = []
for pname, pdata in pi['providers'].items():
    if pname in providers:
        key = pname
    elif ALIAS.get(pname) in providers:
        key = ALIAS[pname]
    else:
        key = {norm(k): k for k in providers}.get(norm(pname))
    if key is None:
        out.append(f'跳过 {pname}: dsh 无对应 provider')
        continue
    prov = providers[key]
    if not prov.get('baseURL'):  # 规则：不更新已有值，仅空值补充
        prov['baseURL'] = pdata.get('baseUrl', '')
        out.append(f'{pname}: baseURL 空值补充')
    if not prov.get('api'):
        prov['api'] = pdata.get('api', 'openai-completions')
        out.append(f'{pname}: api 空值补充')
    models = prov.setdefault('models', [])
    existing = {m['id'] for m in models if isinstance(m, dict)}
    added = []
    for item in pdata.get('models', []):
        mid = item['id']
        if mid in existing:
            continue
        models.append({'id': mid})
        added.append(mid)
    out.append(f'{pname}: 新增模型 {len(added)} 个 {added if added else ""}')

with open(DSH_PATH, 'w') as f:
    yaml.safe_dump(dsh, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

bak = yaml.safe_load(open(DSH_PATH + '.bak-' + stamp))
bprov, cprov = bak['llm-pi-ai']['providers'], providers
assert list(bprov.keys()) == list(cprov.keys()), 'provider 键序被改动'
for k in cprov:
    bm = [m for m in bprov[k].get('models', []) if isinstance(m, dict)]
    cm = [m for m in cprov[k].get('models', []) if isinstance(m, dict)]
    assert all(m in cm for m in bm), f'{k}: 现有模型条目被改动'
    for kk, vv in bprov[k].items():
        if kk == 'models':
            continue
        if kk in ('baseURL', 'api'):
            assert cprov[k].get(kk) == vv or (not vv and cprov[k].get(kk)), f'{k}: {kk} 被改动（已有值）'
        else:
            assert cprov[k].get(kk) == vv, f'{k}: 字段 {kk} 被改动'
print('校验通过：仅 models 新增')
print('\n'.join(out))