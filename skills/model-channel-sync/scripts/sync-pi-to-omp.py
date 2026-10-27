#!/usr/bin/env python3
"""pi → omp 同步（合并式：保留现有 + 补 pi 缺失模型；pi 新渠道自动创建 provider）。

用法:
    python3 scripts/sync-pi-to-omp.py

omp 的 apiKey 为环境变量名裸形式（env 名可能与 pi 不同，如 kilo 用
NVIDIA_API_KEY 而 pi 用 KILO_API_KEY），已有 provider 保留不动，避免破坏连接；
pi 中存在但 omp 无对应的渠道自动创建 provider（baseUrl 明文、apiKey 从 pi 的
!echo -n "$VAR" 提取 env 变量名）。只同步 models（YAML 列表，元素 {id, name}）。
pi 条目提供 contextWindow/maxTokens 限制时，新增条目一并写入，现有条目不一致即同步更新
（来源为权威值）。例外——Sense 渠道（token.sensenova.cn / token.sensenova.ai）：写入 omp 的
模型条目不携带 reasoning 与 maxTokens 两个参数，已有条目中的这两个参数一并移除
（contextWindow 等其它参数照常）。幂等可重复执行；自动备份（.bak-YYYYMMDD）；断言校验只允许
models 新增、限制字段同步、参数精简、空值补充与新渠道创建；密钥不回显。
"""
import json, re, os, shutil, datetime, sys
from urllib.parse import urlparse
import yaml

sys.dont_write_bytecode = True  # 不生成 __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pi_cache

OMP_PATH = os.path.expanduser('~/.omp/agent/models.yml')

# Sense 渠道参数精简：写入 omp 的模型条目不携带 reasoning/maxTokens，已有条目中的这两个参数一并删除；
# 按 baseUrl 主机判定（token.sensenova.cn / token.sensenova.ai），渠道 key 可能被改名，不按 key 判定
SENSE_HOSTS = ('token.sensenova.cn', 'token.sensenova.ai')
STRIP_PARAMS = ('maxTokens', 'reasoning')


def is_sense(url):
    """baseUrl 主机命中 Sense 渠道上游（token.sensenova.cn / token.sensenova.ai）时返回 True。"""
    if not url:
        return False
    try:
        return (urlparse(url).hostname or '') in SENSE_HOSTS
    except ValueError:
        return False


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


stamp = datetime.date.today().strftime('%Y%m%d')
shutil.copy(OMP_PATH, OMP_PATH + '.bak-' + stamp)
pi = pi_cache.load()
omp = yaml.safe_load(open(OMP_PATH))
providers = omp['providers']

out = []
srclim_by_key = {}  # provider key → {模型 id: {contextWindow?, maxTokens?}}（限制同步的断言放行依据）
sense_by_key = {}   # provider key → bool（是否 Sense 渠道）
for pname, pdata in pi['providers'].items():
    if pname in providers:
        key = pname
    else:
        key = {norm(k): k for k in providers}.get(norm(pname))
    if key is None:
        # pi 中存在但 omp 无对应渠道 → 自动创建 provider
        # baseUrl 明文、api 从 pi 取、apiKey 从 pi 的 !echo -n "$VAR" 提取 env 变量名（omp 裸形式）
        m = re.match(r'!echo -n "\$([A-Z0-9_]+)"', pdata.get('apiKey', ''))
        env_name = m.group(1) if m else pdata.get('apiKey', '')
        prov = {
            'baseUrl': pdata.get('baseUrl', ''),
            'api': pdata.get('api', 'openai-completions'),
            'apiKey': env_name,
            'models': []
        }
        providers[pname] = prov
        key = pname
        out.append(f'{pname}: 新建 provider（baseUrl 明文, apiKey: {env_name}）')
    else:
        prov = providers[key]
        if not prov.get('baseUrl'):  # 规则：不更新已有值，仅空值补充
            prov['baseUrl'] = pdata.get('baseUrl', '')
            out.append(f'{pname}: baseUrl 空值补充')
        if not prov.get('api'):
            prov['api'] = pdata.get('api', 'openai-completions')
            out.append(f'{pname}: api 空值补充')
    models = prov.setdefault('models', [])
    existing = {m['id'] for m in models if isinstance(m, dict)}
    added = []
    limupd = []
    srclim = {}
    sense = is_sense(prov.get('baseUrl')) or is_sense(pdata.get('baseUrl'))
    sense_by_key[key] = sense
    # 模型失效过滤：/models 可读渠道剔除实时列表中已不存在的模型（no_models_api 渠道以 pi 列表为准）
    items, dropped = pi_cache.filter_models(pi, pname, pdata.get('models', []))
    if dropped:
        out.append(f'{pname}: 剔除失效模型 {dropped}（实时 /models 不再存在）')
    for item in items:
        mid = item['id']
        lim = {k: item[k] for k in ('contextWindow', 'maxTokens') if item.get(k)}
        if sense:
            lim.pop('maxTokens', None)  # Sense 渠道：条目不携带 maxTokens/reasoning
            # 断言放行依据：这两个参数允许被删除（值记为 None）
            srclim[mid] = {**dict.fromkeys(STRIP_PARAMS, None), **lim}
        elif lim:
            srclim[mid] = lim
        if mid not in existing:
            entry = {'id': mid, 'name': item.get('name', mid)}
            entry.update(lim)
            models.append(entry)
            added.append(mid)
        else:
            for mm in models:
                if isinstance(mm, dict) and mm.get('id') == mid:
                    for lk in (STRIP_PARAMS if sense else ()):  # Sense 渠道：存量条目参数一并移除
                        if lk in mm:
                            limupd.append(f'{mid}.{lk} 移除')
                            del mm[lk]
                    for lk, lv in lim.items():
                        if mm.get(lk) != lv:
                            limupd.append(f'{mid}.{lk} {mm.get(lk)}→{lv}')
                            mm[lk] = lv
    srclim_by_key[key] = srclim
    if limupd:
        out.append(f'{pname}: 限制同步 {len(limupd)} 项 {limupd}')
    out.append(f'{pname}: 新增模型 {len(added)} 个 {added if added else ""}')

with open(OMP_PATH, 'w') as f:
    yaml.safe_dump(omp, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

bak = yaml.safe_load(open(OMP_PATH + '.bak-' + stamp))
bprov, cprov = bak['providers'], providers
assert list(bprov.keys()) == list(cprov.keys())[:len(bprov)], 'provider 键序被改动（已有键顺序变化）'
assert set(bprov.keys()) <= set(cprov.keys()), '已有 provider 被删除'
for k in cprov:
    if k not in bprov:
        continue  # 新建 provider 不做后备对比断言
    bm = [m for m in bprov[k].get('models', []) if isinstance(m, dict)]
    cm = [m for m in cprov[k].get('models', []) if isinstance(m, dict)]
    bidx = {m['id']: m for m in bm}
    cidx = {m['id']: m for m in cm}
    allow_all = srclim_by_key.get(k, {})
    # Sense 渠道：存量条目允许移除 reasoning/maxTokens（在白名单内放行）
    strip = STRIP_PARAMS if sense_by_key.get(k) else ()
    excl = tuple(dict.fromkeys(('contextWindow', 'maxTokens') + strip))
    for bid, bmv in bidx.items():
        if bid not in cidx:
            assert False, f'{k}: 现有模型条目 {bid} 被删除'
        cmv = cidx[bid]
        allow = allow_all.get(bid, {})
        for lk in excl:
            if bmv.get(lk) != cmv.get(lk):
                assert allow.get(lk) == cmv.get(lk), \
                    f'{k}: 现有模型条目 {bid} 的 {lk} 被改动（无来源依据）'
        assert {kk: vv for kk, vv in bmv.items() if kk not in excl} == \
               {kk: vv for kk, vv in cmv.items() if kk not in excl}, \
            f'{k}: 现有模型条目 {bid} 被改动'
    for kk, vv in bprov[k].items():
        if kk == 'models':
            continue
        if kk in ('baseUrl', 'api'):
            assert cprov[k].get(kk) == vv or (not vv and cprov[k].get(kk)), f'{k}: {kk} 被改动（已有值）'
        else:
            assert cprov[k].get(kk) == vv, f'{k}: 字段 {kk} 被改动'
print('校验通过：仅 models 新增 / 限制字段同步 / Sense 参数精简 / 空值补充 / 新渠道创建')
print('\n'.join(out))