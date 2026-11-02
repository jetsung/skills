#!/usr/bin/env python3
"""pi → opencode 同步（合并式：保留现有 + 补 pi 缺失模型）。

用法:
    python3 scripts/sync-pi-to-opencode.py

opencode v2 配置(https://opencode.ai/v2/docs/migrate-v1/)apiKey 为 {env:XXX} 占位符,保留不动;
只同步 models(对象 map,key = 模型 id,value = {modelID, name, family},family 规则 = id 前缀或渠道名)。
provider 缺失 package 时补默认适配器 `aisdk:@ai-sdk/openai-compatible`(插在 settings 之前),已有值不动。
pi 条目提供 contextWindow/maxTokens 限制时,新增条目写入 `limit.context/limit.output`,
现有条目不一致即同步更新(来源为权威值)。
幂等可重复执行;自动备份(.bak-YYYYMMDD);断言校验只允许 models 新增、限制字段同步与 package 空值补充;密钥不回显。
"""
import json, re, os, shutil, datetime, sys

sys.dont_write_bytecode = True  # 不生成 __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pi_cache

OC_PATH = os.path.expanduser('~/.config/opencode/opencode.json')
ALIAS = {'cloudflare-workers-ai': 'cloudflare-workers-ai'}  # 与 pi 同名，保留可扩展
PKG_DEFAULT = 'aisdk:@ai-sdk/openai-compatible'


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def ensure_package(prov):
    """provider 缺失/为空时补 package 默认适配器，插在 settings 之前；已有值不动。返回是否补入。"""
    if prov.get('package'):
        return False
    items = list(prov.items())
    prov.clear()
    inserted = False
    for k, v in items:
        if k == 'settings' and not inserted:
            prov['package'] = PKG_DEFAULT
            inserted = True
        prov[k] = v
    if not inserted:
        prov['package'] = PKG_DEFAULT
    return True


REPLACE = '--replace' in sys.argv  # 完全替换：删除 pi 没有的渠道/模型
KEEP_CHANNELS = {'magpie'}
stamp = datetime.date.today().strftime('%Y%m%d')
shutil.copy(OC_PATH, OC_PATH + '.bak-' + stamp)
pi = pi_cache.load()
oc = json.load(open(OC_PATH))
providers = oc['providers']

out = []
srclim_by_key = {}  # provider key → {模型 id: {context?, output?}}（限制同步的断言放行依据）
if REPLACE:
    pi_keys = {norm(k) for k in pi['providers']}
    removed_ch = []
    for k in list(providers):
        if norm(k) not in pi_keys and k not in KEEP_CHANNELS:
            removed_ch.append(k)
            del providers[k]
    if removed_ch:
        out.append('删除渠道（pi 基准无此渠道）: ' + '、'.join(removed_ch))
    removed_m = {}
    for pname, pdata in pi['providers'].items():
        key = pname if pname in providers else {norm(k): k for k in providers}.get(norm(pname))
        if key is None:
            continue
        pi_mids = {m['id'] for m in pdata.get('models', []) if isinstance(m, dict)}
        models = providers[key].get('models', {})
        gone = [mid for mid in models if mid not in pi_mids]
        providers[key]['models'] = {mid: mv for mid, mv in models.items() if mid in pi_mids}
        if gone:
            removed_m[key] = gone
    for k, gone in removed_m.items():
        out.append(f'{k}: 删除模型 {len(gone)} 个 {gone}')
for pname, pdata in pi['providers'].items():
    if pname in providers:
        key = pname
    elif ALIAS.get(pname) in providers:
        key = ALIAS[pname]
    else:
        key = {norm(k): k for k in providers}.get(norm(pname))
    if key is None:
        # pi 存在但 opencode 无对应渠道 → 自动创建 provider（完全替换/合并均适用）
        if pi_cache.no_auto_add(pname):
            out.append(f'跳过 {pname}: 禁止自动新建渠道（opencode/openrouter 需显式声明）')
            continue
        m = re.match(r'!echo -n "\$([A-Z0-9_]+)"', pdata.get('apiKey', ''))
        env_name = m.group(1) if m else ''
        prov = {
            'name': pname + ' Custom',
            'package': PKG_DEFAULT,
            'settings': {
                'apiKey': '{env:' + env_name + '}' if env_name else '',
                'baseURL': pdata.get('baseUrl', ''),
            },
            'models': {},
        }
        providers[pname] = prov
        key = pname
        out.append(f'{pname}: 新建 provider（{PKG_DEFAULT}）')
    prov = providers[key]
    if ensure_package(prov):
        out.append(f'{pname}: package 空值补充（{PKG_DEFAULT}）')
    opts = prov.setdefault('settings', {})
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
    # 模型失效过滤：/models 可读渠道剔除实时列表中已不存在的模型（no_models_api 渠道以 pi 列表为准）
    items, dropped = pi_cache.filter_models(pi, pname, pdata.get('models', []))
    note = pi_cache.dropped_note(pname, dropped)
    if note:
        out.append(note)
    for item in items:
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
            entry = {'modelID': mid, 'name': item.get('name', mid), 'family': family}
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
if REPLACE:
    keep_keys = [k for k in bak['providers'] if k in providers]
    assert [k for k in providers if k in bak['providers']] == keep_keys, '保留 provider 键序被改动'
else:
    assert list(bak['providers'].keys()) == list(providers.keys()), 'provider 键序被改动'
for k in providers:
    if k not in bak['providers']:
        continue  # 新建 provider 不做后备对比断言
    b, c = bak['providers'][k], providers[k]
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
    assert {kk: vv for kk, vv in b.items() if kk not in ('models', 'settings', 'package')} == \
           {kk: vv for kk, vv in c.items() if kk not in ('models', 'settings', 'package')}, f'{k}: 非 models/settings/package 字段被改动'
    if b.get('package'):
        assert c.get('package') == b['package'], f'{k}: package 已有值被改动'
    else:
        assert c.get('package') in (None, '', PKG_DEFAULT), f'{k}: package 被非法改动'
    bo, co = b.get('settings', {}), c.get('settings', {})
    for kk, vv in bo.items():
        if kk == 'baseURL':
            assert co.get('baseURL') == vv or (not vv and co.get('baseURL')), f'{k}: baseURL 被改动（已有值）'
        else:
            assert co.get(kk) == vv, f'{k}: options.{kk} 被改动'
print('校验通过：仅 models 新增 / 限制字段同步 / package 空值补充')
print('\n'.join(out))
