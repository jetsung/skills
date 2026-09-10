#!/usr/bin/env python3
"""pi → zcode 全量同步（合并式：保留 zcode 现有 + 补 pi 缺失 + 更新 apiKey）。

用法:
    python3 scripts/sync-pi-to-zcode.py

按需修改下方 PI_PATH / ZC_PATH / ALIAS。
规则：
- baseURL / kind（兼容模式）：**不更新已有值**，仅当目标缺失/为空时从 pi 补入
  （kind 由 pi 的 api 字段映射：openai-completions → openai-compatible，anthropic → anthropic）
- apiKey：解析 pi 的 !echo -n "$VAR" 读环境变量，写入明文 options.apiKey
- models：合并（保留 zcode 现有 + 补 pi 缺失），幂等；来源（上游 API / pi 配置）提供 context/max_output
  限制时，新增条目写入 `limit.context/limit.output`，现有条目不一致即同步更新（来源为权威值）
幂等可重复执行；自动备份（.bak-YYYYMMDD）并断言校验；密钥不回显。
"""
import json, re, os, shutil, datetime
import fetch_free

PI_PATH = os.path.expanduser('~/.pi/agent/models.json')
ZC_PATH = os.path.expanduser('~/.zcode/v2/config.json')
ALIAS = {'cloudflare-workers-ai': 'CloudFlare AI'}  # 规范化后不匹配的渠道手动映射
KIND_MAP = {'openai-completions': 'openai-compatible', 'anthropic': 'anthropic'}
# kilo/openrouter 渠道不走 pi models 基准，改从上游 API 提取免费模型（含价格 0，剔除图像/视频类）；
# opencode 渠道不同步（上游价格数据不正确）
UPSTREAM_FREE = ('kilo', 'openrouter')
# 不同步的渠道（pi 中存在但明确排除，如 opencode 上游价格数据不正确）
SKIP_CHANNELS = ('opencode',)


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


stamp = datetime.date.today().strftime('%Y%m%d')
shutil.copy(ZC_PATH, ZC_PATH + '.bak-' + stamp)
pi = json.load(open(PI_PATH))
zc = json.load(open(ZC_PATH))
zname2key = {norm(p['name']): k for k, p in zc['provider'].items() if 'name' in p}

out = []
srclim_by_key = {}  # provider key → {模型 id: {context?, output?}}（限制同步的断言放行依据）
for pname, pdata in pi['providers'].items():
    if pname in SKIP_CHANNELS:
        out.append(f'跳过 {pname}: 不同步（价格数据不正确）')
        continue
    key = zname2key.get(norm(ALIAS.get(pname, pname)))
    if key is None:
        out.append(f'跳过 {pname}: zcode 无对应 provider')
        continue
    prov = zc['provider'][key]
    # 模型源：kilo/opencode/openrouter 从上游提取免费模型，其他渠道用 pi models
    if pname in UPSTREAM_FREE:
        try:
            items = fetch_free.fetch_free_models(pname)
        except Exception as e:
            items = pdata.get('models', [])
            out.append(f'{pname}: 上游提取失败（{e}），回退 pi models')
    else:
        items = pdata.get('models', [])
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
    limupd = []
    srclim = {}  # 模型 id → 来源提供的限制（limit 同步的断言放行依据）
    for item in items:
        lim = {}
        if item.get('contextWindow'):
            lim['context'] = item['contextWindow']
        if item.get('maxTokens'):
            lim['output'] = item['maxTokens']
        if lim:
            srclim[item['id']] = lim
        if item['id'] not in existing:
            entry = {'name': item.get('name', item['id'])}
            if lim:
                entry['limit'] = lim
            entry['zcode'] = {'modified': True, 'priority': nxt}
            prov['models'][item['id']] = entry
            nxt += 1
            added.append(item['id'])
        elif lim and isinstance(prov['models'].get(item['id']), dict):
            # 限制同步：来源（上游 API / pi）值为权威，不一致即改写
            tl = prov['models'][item['id']].setdefault('limit', {})
            for lk, lv in lim.items():
                if tl.get(lk) != lv:
                    limupd.append(f'{item["id"]}.limit.{lk} {tl.get(lk)}→{lv}')
                    tl[lk] = lv
    srclim_by_key[key] = srclim
    if limupd:
        out.append(f'{pname}: 限制同步 {len(limupd)} 项 {limupd}')
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
    for mk, mv in bm.items():
        if mk not in cm:
            continue
        bv = {kk: vv for kk, vv in mv.items() if kk != 'limit'} if isinstance(mv, dict) else mv
        cv = {kk: vv for kk, vv in cm[mk].items() if kk != 'limit'} if isinstance(cm[mk], dict) else cm[mk]
        assert bv == cv, f'{k}: 现有模型条目 {mk} 被改动'
        blim = (mv.get('limit') or {}) if isinstance(mv, dict) else {}
        clim = (cm[mk].get('limit') or {}) if isinstance(cm[mk], dict) else {}
        allow = srclim_by_key.get(k, {}).get(mk, {})
        for lk, lv in clim.items():
            if blim.get(lk) != lv:
                assert allow.get(lk) == lv, \
                    f'{k}: 现有模型条目 {mk} 的 limit.{lk} 被改动（无来源依据）'
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
print('校验通过：仅 models 新增 / apiKey 更新 / 空值补充 baseURL+kind+limit')
print('\n'.join(out))