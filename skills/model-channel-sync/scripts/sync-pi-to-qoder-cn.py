#!/usr/bin/env python3
"""pi → qoder-cn 全量同步（渠道独立式：每渠道独立 provider、独立密钥、模型按渠道归属）。

用法:
    python3 scripts/sync-pi-to-qoder-cn.py

按需修改下方 PI_PATH / QODER_PATH / ALIAS / TARGET / CHANNEL_DISPLAY。
规则：
- **渠道匹配**：baseUrl 去尾斜杠强绑定（唯一）→ ALIAS 显式映射 → 规范化 displayName（仅未占用 provider）；
  无匹配渠道**自动创建**新 provider（key=qoder-custom-{uuid4}，结构与现有条目一致）
- **独立密钥**：每个 provider 只写自己归属渠道的 apiKey（env 解析，正则含数字），互不覆盖
- **模型归属**：模型去供应商前缀后的短 id 属于哪个渠道就归哪个渠道；provider 同步后只保留
  归属渠道的目标模型 + 用户手动添加的不属于任何渠道的模型，其它渠道的模型迁出（由各自渠道的 provider 接管）
- **模型筛选**：openrouter/opencode 渠道只补**免费模型**（id 含 `:free`/`-free`/`/free`），其它渠道**全量同步**
  pi 的所有模型（无模型族限制）；newapi 等中转渠道的模型（如 sense/deepseek-latest-flash）
  即使 id 前缀与其它渠道同名（sense/deepseek-v4-flash）也是独立模型，归 newapi
- **模型 id**：保持 pi 原有 id 原样，不得擅自添加任何前缀（如 sense 渠道的 `deepseek-v4-flash` 就是 `deepseek-v4-flash`，不写 `sense/deepseek-v4-flash`；newapi 渠道的 `amd/deepseek-latest-flash` 本身带前缀则原样保留）
- **displayName**：baseUrl 匹配/新建时更新为渠道显示名（纠正错误归属）；弱匹配（ALIAS/displayName）时已有值保留、空值补充
- **兼容模式**：baseUrl / type / protocol / authType **不更新已有值**；新建时按现有条目格式初始化
- **默认模型（model 字段）版本族规则**：族键 = 模型 id 取最后一个 `/` 后的段（无 `/` 取全段）小写后的开头连续字母（`^[a-z]+`，提取不到用整段）；
  版本号 = 该段首个数字串（`agnes-2.5-flash` → 族 `agnes`、版本 `(2, 5)`；无数字 → `()`）。models 中同族存在更高版本时，
  model 自动升级为同族最高版本（如 agnes-2.0/2.5/3.0-flash 用 agnes-3.0-flash）；model 为空时取首个模型同族最高版本；同版本/无版本号一律不动
幂等可重复执行；自动备份（.bak-YYYYMMDD）并断言校验；密钥不回显。
"""
import json, re, os, shutil, datetime, uuid
import fetch_free

PI_PATH = os.path.expanduser('~/.pi/agent/models.json')
QODER_PATH = os.path.expanduser('~/.qoder-cn/settings.json')
ALIAS = {}  # 规范化 displayName 兜底失败时的手动映射，如 {'newapi': 'Qoder Custom ...'}
# kilo/openrouter 渠道不走 pi models 基准，改从上游 API 提取免费模型（含价格 0，剔除图像/视频类）；
# opencode 渠道不同步（上游价格数据不正确）
UPSTREAM_FREE = ('kilo', 'openrouter')
SKIP_CHANNELS = ('opencode',)
# 免费渠道：这些渠道只同步免费模型（id 含 :free/-free//free，如 openrouter 的 xx:free）
FREE_CHANNELS = ('openrouter',)
# 渠道 key → 渠道显示名（用于 displayName 前缀，如 newapi → NewAPI）
CHANNEL_DISPLAY = {
    'sense': 'Sense', 'amd': 'AMD', 'ds2api': 'DS2API', 'newapi': 'NewAPI',
    'agnes': 'Agnes', 'cloudflare-workers-ai': 'Cloudflare Workers AI',
    'atomgit': 'AtomGit', 'kilo': 'Kilo', 'v2ex': 'V2EX', 'colab': 'Colab',
    'opencode': 'OpenCode', 'openrouter': 'OpenRouter', 'inferx': 'InferX',
    'tokenrouter': 'TokenRouter',
}
# 顶层不可变字段（兼容模式：不更新已有值；model 为当前选中，允许去前缀规范化与版本族升级）
IMMUTABLE = ('baseUrl', 'type', 'protocol', 'authType')


def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def short_id(mid):
    return mid.split('/')[-1].lower()


FAM_RE = re.compile(r'^[a-z]+')
VER_RE = re.compile(r'\d+(?:\.\d+)*')


def fam_key(mid):
    """版本族键：id 最后一个 / 后的段（无 / 取全段）小写后提取开头连续字母；提取不到用整段"""
    s = (mid or '').rsplit('/', 1)[-1].lower()
    g = FAM_RE.match(s)
    return g.group() if g else s


def ver_key(mid):
    """版本号键：id 最后一段的首个数字串（agnes-2.5-flash → (2, 5)）；无数字 → ()"""
    g = VER_RE.search((mid or '').rsplit('/', 1)[-1].lower())
    return tuple(int(x) for x in g.group().split('.')) if g else ()

def wanted(item, pname):
    """模型筛选：openrouter/opencode 渠道只同步免费模型（id 含 free）；其他渠道全量同步"""
    if pname in FREE_CHANNELS:
        mid = item['id'].lower()
        return ':free' in mid or '-free' in mid or '/free' in mid
    return True


def vendor_disp(item, pname):
    """模型所属渠道显示名（前缀用渠道名，如 newapi → NewAPI；模型名自带供应商信息）"""
    return CHANNEL_DISPLAY.get(pname, pname)


def display_name(item, pname):
    """模型显示名：渠道显示名 + ' - ' + 模型名（模型名已以渠道名开头则去掉重复前缀）。
    例：newapi 的 "AMD DeepSeek Latest Flash" → "NewAPI - AMD DeepSeek Latest Flash"；
        amd 的 "AMD DeepSeek V4 Flash" → "AMD - DeepSeek V4 Flash"（去重）"""
    disp = vendor_disp(item, pname)
    mname = item.get('name', item['id'])
    if mname.lower().startswith(disp.lower()):
        mname = mname[len(disp):].strip()
    return f'{disp} - {mname}'


stamp = datetime.date.today().strftime('%Y%m%d')
shutil.copy(QODER_PATH, QODER_PATH + '.bak-' + stamp)
pi = json.load(open(PI_PATH))
qc = json.load(open(QODER_PATH))

# 渠道短 id 索引（模型归属判定）
channel_ids = {pname: {short_id(m['id']) for m in pdata.get('models', [])}
               for pname, pdata in pi['providers'].items()}
# 渠道 baseUrl 索引（去尾斜杠；用于 baseUrl 强绑定与 displayName 匹配约束）
baseurl_to_channel = {}
for pname, pdata in pi['providers'].items():
    b = (pdata.get('baseUrl') or '').rstrip('/')
    if b:
        baseurl_to_channel.setdefault(b, pname)

# 上游免费渠道的模型 id 索引（这些模型归对应渠道 provider 所有，参与归属判定时豁免）
upstream_ids = {}
upstream_short_ids = set()
for _pn in UPSTREAM_FREE:
    try:
        _items = fetch_free.fetch_free_models(_pn)
    except Exception:
        _items = []
    upstream_ids[_pn] = {i['id'] for i in _items}
    upstream_short_ids |= {i['id'].split('/')[-1].lower() for i in _items}


def owned_by_other(pname, prov):
    """provider 的 baseUrl 是否归属其他渠道（若是，该 provider 只能由 baseUrl 渠道占用）"""
    b = (prov.get('baseUrl') or '').rstrip('/')
    return b in baseurl_to_channel and baseurl_to_channel[b] != pname


def owner_of(mid):
    """模型 id 归属哪个渠道（去供应商前缀后匹配短 id；只认目标模型所属渠道）。
    kilo/opencode/openrouter 渠道的上游免费模型由对应 provider 自行接管，不做归属判定"""
    if mid in upstream_ids.get(None, set()) or short_id(mid) in upstream_short_ids:
        return None
    s = short_id(mid)
    for pn, ids in channel_ids.items():
        if s in ids:
            return pn
    return None


def new_provider(pname, pdata, env_val, items):
    """按现有条目格式新建 provider（key=qoder-custom-{uuid4}）；items 为已过滤的目标模型"""
    first = items[0] if items else {}
    return {
        'baseUrl': pdata.get('baseUrl', ''),
        'apiKey': env_val,
        'type': 'openai-compatible',
        'protocol': 'openai',
        'authType': 'bearer',
        'model': first.get('id', '') if first else '',
        'models': [{
            'model': i['id'],
            'displayName': display_name(i, pname),
            'contextWindow': 200000,
            'maxOutputTokens': 8192,
            'capabilities': {'vision': False,
                             'thinking': {'modes': [], 'supportsEffort': False,
                                          'supportedEffortLevels': []}},
        } for i in items],
        'displayName': CHANNEL_DISPLAY.get(pname, pname),
    }


out = []
occupied = set()
for pname, pdata in pi['providers'].items():
    if pname in SKIP_CHANNELS:
        out.append(f'跳过 {pname}: 不同步（价格数据不正确）')
        continue
    # 模型源：kilo/openrouter 从上游提取免费模型，其他渠道用 pi models
    if pname in UPSTREAM_FREE:
        try:
            src_models = fetch_free.fetch_free_models(pname)
        except Exception as e:
            src_models = pdata.get('models', [])
            out.append(f'{pname}: 上游提取失败（{e}），回退 pi models')
    else:
        src_models = pdata.get('models', [])
    items = [i for i in src_models if wanted(i, pname)]
    if not items:
        out.append(f'跳过 {pname}: 无模型（空列表，或免费渠道过滤后为空）')
        continue
    # 1) baseUrl 去尾斜杠强绑定
    burl = (pdata.get('baseUrl') or '').rstrip('/')
    key = how = None
    if burl:
        for k, p in qc['providers'].items():
            if (p.get('baseUrl') or '').rstrip('/') == burl:
                key, how = k, 'baseurl'
                break
    # 2) ALIAS 显式映射（未占用且未被其他渠道 baseUrl 强绑定）
    if key is None and pname in ALIAS:
        t = norm(ALIAS[pname])
        for k, p in qc['providers'].items():
            if k not in occupied and not owned_by_other(pname, p) and norm(p.get('displayName')) == t:
                key, how = k, 'alias'
                break
    # 3) 规范化 displayName 匹配（未占用且未被其他渠道 baseUrl 强绑定）
    if key is None:
        t = norm(pname)
        for k, p in qc['providers'].items():
            if k not in occupied and not owned_by_other(pname, p) and norm(p.get('displayName')) == t:
                key, how = k, 'displayname'
                break
    # 4) 无匹配 → 自动创建
    m = re.match(r'!echo -n "\$([A-Z0-9_]+)"', pdata.get('apiKey', ''))
    env_val = os.environ[m.group(1)] if (m and os.environ.get(m.group(1))) else ''
    if key is None:
        key = 'qoder-custom-' + str(uuid.uuid4())
        qc['providers'][key] = new_provider(pname, pdata, env_val, items)
        how = 'created'
        out.append(f'{pname}: 自动创建 provider（{key}）')
    occupied.add(key)
    prov = qc['providers'][key]

    # 模型归属：保留本渠道目标模型 + 不属于任何渠道的模型（用户手动添加），其它渠道模型迁出
    kept, migrated = [], []
    for mm in prov.get('models', []):
        mid = mm['model']
        own = owner_of(mid)
        if short_id(mid) in channel_ids.get(pname, ()) or own is None:
            kept.append(mm)
        else:
            migrated.append(f'{mid}（属 {own} 渠道）')
    prov['models'] = kept
    if migrated:
        out.append(f'{pname}: 迁出 {len(migrated)} 个模型 {migrated}')
    # 去重（按 model id，保留首个；历史误加前缀/重复条目在此收敛）
    seen, uniq = set(), []
    for mm in prov['models']:
        if mm['model'] in seen:
            continue
        seen.add(mm['model'])
        uniq.append(mm)
    if len(uniq) != len(prov['models']):
        out.append(f'{pname}: 去重 {len(prov["models"]) - len(uniq)} 个重复模型')
    prov['models'] = uniq

    # 模型 id 规范化：去掉本渠道擅自添加的前缀（pi 原有 id 无前缀的还原；本身带前缀的如 newapi 的 amd/... 不动）
    for mm in prov['models']:
        mid = mm['model']
        if mid.startswith(pname + '/'):
            short = mid[len(pname) + 1:]
            if short.lower() in channel_ids.get(pname, ()):  # 短 id 索引为小写，比较时 lower
                mm['model'] = short
    # 当前选中模型同样规范化
    if prov.get('model', '').startswith(pname + '/'):
        short = prov['model'][len(pname) + 1:]
        if short.lower() in channel_ids.get(pname, ()):
            prov['model'] = short

    # 补缺失的目标模型 + 规范现有目标模型的 displayName（渠道前缀格式，幂等）
    existing = {mm['model'] for mm in prov['models']}
    ref = next((mm for mm in prov['models'] if isinstance(mm, dict)), {})
    ctx = ref.get('contextWindow', 200000)
    mout = ref.get('maxOutputTokens', 8192)
    added, renamed = [], []
    for item in src_models:
        if not wanted(item, pname):
            continue
        mid = item['id']
        want = display_name(item, pname)
        if mid in existing:
            for mm in prov['models']:
                if mm['model'] == mid and mm.get('displayName') != want:
                    mm['displayName'] = want
                    renamed.append(mid)
            continue
        prov['models'].append({
            'model': mid,
            'displayName': want,
            'contextWindow': ctx,
            'maxOutputTokens': mout,
            'capabilities': {'vision': False,
                             'thinking': {'modes': [], 'supportsEffort': False,
                                          'supportedEffortLevels': []}},
        })
        existing.add(mid)
        added.append(mid)

    # 默认模型（model）版本族规则：选中模型同族存在更高版本 → 升级到同族最高版本；
    # 选中为空 → 取首个模型同族的最高版本；同版本或均无版本号一律不动（幂等）
    model_ids = [mm['model'] for mm in prov['models']]
    cur = prov.get('model', '')
    base = cur if cur in model_ids else (model_ids[0] if model_ids else '')
    if base:
        same = [m for m in model_ids if fam_key(m) == fam_key(base)]
        best = max(same, key=ver_key)
        if best != cur and (cur == '' or ver_key(best) > ver_key(cur)):
            out.append(f'{pname}: 默认模型 {cur or "(空)"} → {best}（{fam_key(base)} 族最高版本）')
            prov['model'] = best

    # displayName：baseUrl/新建时更新为渠道显示名（纠正归属）；弱匹配已有值保留、空值补充
    disp = CHANNEL_DISPLAY.get(pname, pname)
    if how in ('baseurl', 'created'):
        if prov.get('displayName') != disp:
            prov['displayName'] = disp
            out.append(f'{pname}: provider displayName 更新为 {disp}')
    elif not prov.get('displayName'):
        prov['displayName'] = disp
        out.append(f'{pname}: provider displayName 补充为 {disp}')

    # apiKey：只写归属渠道的 env 值（独立密钥）
    if m and os.environ.get(m.group(1)):
        changed = prov.get('apiKey') != env_val
        prov['apiKey'] = env_val
        ren = f' 规范displayName {len(renamed)} 个' if renamed else ''
        out.append(f'{pname}: apiKey {"更新" if changed else "一致"} 新增模型 {len(added)} 个{ren} {added if added else ""}')
    else:
        ren = f' 规范displayName {len(renamed)} 个' if renamed else ''
        out.append(f'{pname}: apiKey 跳过（env 未设置/非占位符） 新增模型 {len(added)} 个{ren}')

with open(QODER_PATH, 'w') as f:
    json.dump(qc, f, ensure_ascii=False, indent=2)
    f.write('\n')

bak = json.load(open(QODER_PATH + '.bak-' + stamp))
# 断言：原键序保留（新键追加）；baseUrl/type/protocol/authType 不变（model 允许去前缀规范化与版本族升级）；
# models 允许新增（目标模型）与迁出（属其他渠道的模型）；apiKey/displayName 允许变
bkeys = list(bak['providers'].keys())
ckeys = list(qc['providers'].keys())
assert [k for k in ckeys if k in bkeys] == bkeys, 'providers 键序被改动'
for k in ckeys:
    if k not in bkeys:
        continue  # 新建 provider
    b, c = bak['providers'][k], qc['providers'][k]
    for kk in IMMUTABLE:
        assert c.get(kk) == b.get(kk), f'{k}: {kk} 被改动（已有值不可变）'
    bm = {mm['model']: mm for mm in b.get('models', []) if isinstance(mm, dict)}
    cm = {mm['model']: mm for mm in c.get('models', []) if isinstance(mm, dict)}
    for bmid, bval in bm.items():
        if bmid not in cm:
            assert owner_of(bmid) is not None, f'{k}: 模型 {bmid} 被删除（不属于其它渠道）'
        else:
            # 允许 displayName 规范化（新格式 {渠道显示名} - {模型名}）；其余字段必须不变
            assert {kk: vv for kk, vv in bval.items() if kk not in ('model', 'displayName')} == \
                   {kk: vv for kk, vv in cm[bmid].items() if kk not in ('model', 'displayName')}, \
                f'{k}: 现有模型条目 {bmid} 被改动（仅允许 model/displayName 规范化）'
print('校验通过：渠道独立（baseUrl 强绑定 / 自动创建），仅 models 新增或跨渠道迁移 / apiKey 更新 / displayName 纠正')
print('\n'.join(out))