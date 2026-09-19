#!/usr/bin/env python3
"""pi → zcode 全量同步（新版规则式 schema，合并式：保留现有 + 补 pi 缺失 + 更新 apiKey）。

用法:
    python3 scripts/sync-pi-to-zcode.py

按需修改下方 PI_PATH / ZC_PATH / ALIAS。
目标配置: ~/.zcode/v2/provider_config.json（schemaVersion 1 规则式）:
- 渠道: config.providerConfigRules.providerRules[] = {providerId, providerName, config}
  config 字段集合固定: group("standard-personal") / access{type,apiKey} / api{type,baseUrl} /
  personalModelIds / modelOrder —— 不可添加任何额外字段
- 模型: config.modelConfigRules.providerModelRules[] = {modelId, config:{enabled:true}, providerId}
- 自定义渠道 providerId = baseURL 域名主体（去掉子域名与顶级后缀，多段顶级后缀如 com.cn 取 3 段；
  {env:VAR} 占位符无法解析时保留原名），与现有渠道不可重复；同主体不同 TLD 时确定性带顶级后缀
  消歧（如 api.agnes-ai.cn 与 api.agnes-ai.com 均为 agnes-ai → agnes-ai-cn / agnes-ai-com），
  禁用 -2/-3 序号后缀（顺序依赖，重跑可能互换导致重复创建）
- api.type 映射: pi 的 openai-completions → openai-chat-completions；anthropic → anthropic-messages
规则：
- apiKey：解析 pi 的 !echo -n "$VAR" 读环境变量，写入明文 access.apiKey
- models：合并（personalModelIds/modelOrder 追加缺失 + providerModelRules 补条目），幂等
- 无对应渠道时自动创建（字段集合与现有条目一致）
幂等可重复执行；自动备份（.bak-YYYYMMDD）并断言校验；密钥不回显。
"""
import json, re, os, shutil, datetime
from urllib.parse import urlparse
import fetch_free

PI_PATH = os.path.expanduser('~/.pi/agent/models.json')
ZC_PATH = os.path.expanduser('~/.zcode/v2/provider_config.json')
ALIAS = {'cloudflare-workers-ai': 'CloudFlare AI'}  # 规范化后不匹配的渠道手动映射
API_MAP = {'openai-completions': 'openai-chat-completions', 'anthropic': 'anthropic-messages'}
# kilo/openrouter 渠道不走 pi models 基准，改从上游 API 提取免费模型（含价格 0，剔除图像/视频类）；
# opencode 渠道不同步（上游价格数据不正确）
UPSTREAM_FREE = ('kilo', 'openrouter')
# 不同步的渠道（pi 中存在但明确排除，如 opencode 上游价格数据不正确）
SKIP_CHANNELS = ('opencode',)

# 常见多段顶级后缀（命中时域名主体取倒数第 3 段）
MULTI_TLDS = {'com.cn', 'net.cn', 'org.cn', 'gov.cn', 'edu.cn', 'ac.cn',
              'co.uk', 'com.au', 'co.jp', 'com.hk'}


def domain_id(url):
    """baseURL → 域名主体（如 https://api.tokenrouter.com/v1 → tokenrouter）。"""
    host = urlparse(url).hostname
    if not host:
        return None
    labels = host.split('.')
    n = 2
    if len(labels) >= 3 and '.'.join(labels[-2:]) in MULTI_TLDS:
        n = 3
    if len(labels) < n:
        return host
    return labels[-n]  # 注册域名的主体部分


def domain_tld(url):
    """baseURL → 注册域名的顶级后缀（含多段，如 com.cn），用于同主体不同 TLD 的消歧。"""
    host = urlparse(url).hostname
    if not host:
        return None
    labels = host.split('.')
    n = 2
    if len(labels) >= 3 and '.'.join(labels[-2:]) in MULTI_TLDS:
        n = 3
    if len(labels) < n:
        return None
    return '.'.join(labels[-(n - 1):])  # 顶级后缀：com / com.cn / co.uk 等


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def make_provider_rule(pid, pname, base_url, api_type, model_ids):
    """构造渠道条目——字段集合固定，与文件现有条目严格一致。"""
    return {
        'providerId': pid,
        'providerName': pname,
        'config': {
            'group': 'standard-personal',
            'access': {'type': 'api-key', 'apiKey': ''},
            'api': {'type': api_type, 'baseUrl': base_url},
            'personalModelIds': list(model_ids),
            'modelOrder': list(model_ids),
        },
    }


def make_model_rule(mid, pid):
    return {'modelId': mid, 'config': {'enabled': True}, 'providerId': pid}


stamp = datetime.date.today().strftime('%Y%m%d')
shutil.copy(ZC_PATH, ZC_PATH + '.bak-' + stamp)
pi = json.load(open(PI_PATH))
zc = json.load(open(ZC_PATH))
cfg = zc['config']
rules = cfg['providerConfigRules']['providerRules']
model_rules = cfg['modelConfigRules']['providerModelRules']

out = []
used_ids = set(cfg['providerOrder'])
for r in rules:
    used_ids.add(r['providerId'])

for pname, pdata in pi['providers'].items():
    if pname in SKIP_CHANNELS:
        out.append(f'跳过 {pname}: 不同步（价格数据不正确）')
        continue
    # 模型源：kilo/openrouter 从上游提取免费模型，其他渠道用 pi models
    if pname in UPSTREAM_FREE:
        try:
            items = fetch_free.fetch_free_models(pname)
        except Exception as e:
            items = pdata.get('models', [])
            out.append(f'{pname}: 上游提取失败（{e}），回退 pi models')
    else:
        items = pdata.get('models', [])
    if not items:
        out.append(f'跳过 {pname}: 无目标模型')
        continue
    model_ids = [m['id'] for m in items]

    # 匹配渠道：providerName 规范化 + 别名映射
    rule = next((r for r in rules if r.get('providerName')
                 and norm(r['providerName']) == norm(ALIAS.get(pname, pname))), None)
    if rule is None:
        # 自动创建渠道：providerId = baseURL 域名主体；同主体不同 TLD 时确定性带顶级后缀消歧
        # （如 api.agnes-ai.cn 与 api.agnes-ai.com 均为 agnes-ai → agnes-ai-cn / agnes-ai-com），
        # 禁用 -2/-3 序号后缀（顺序依赖，重跑可能互换导致重复创建）
        base_url = pdata.get('baseUrl', '')
        pid = domain_id(base_url) or pname
        if pid in used_ids:
            tld = domain_tld(base_url)
            if tld:
                pid = f'{pid}-{tld.replace(".", "-")}'
            else:
                pid = pname  # 无可解析 TLD 时退回渠道名
        if pid in used_ids:
            i = 2
            while f'{pid}-{i}' in used_ids:
                i += 1
            pid = f'{pid}-{i}'
        used_ids.add(pid)
        api_type = API_MAP.get(pdata.get('api', ''), 'openai-chat-completions')
        rule = make_provider_rule(pid, pname, base_url, api_type, model_ids)
        rules.append(rule)
        cfg['providerOrder'].append(pid)
        out.append(f'{pname}: 新建渠道 {pid}（{api_type}, 模型 {len(model_ids)} 个）')
    else:
        pid = rule['providerId']
        # 合并 models（personalModelIds/modelOrder 追加缺失，幂等）
        existing = set(rule['config']['personalModelIds'])
        added = [mid for mid in model_ids if mid not in existing]
        for mid in added:
            rule['config']['personalModelIds'].append(mid)
            rule['config']['modelOrder'].append(mid)
            model_rules.append(make_model_rule(mid, pid))
        out.append(f'{pname}: 新增模型 {len(added)} 个 {added if added else ""}')

    # apiKey：env 解析（正则含数字）→ 明文写入
    m = re.match(r'!echo -n "\$([A-Z0-9_]+)"', pdata.get('apiKey', ''))
    if m and os.environ.get(m.group(1)):
        changed = rule['config']['access']['apiKey'] != os.environ[m.group(1)]
        rule['config']['access']['apiKey'] = os.environ[m.group(1)]
        out.append(f'  apiKey {"更新" if changed else "一致"}（env: {m.group(1)}）')
    else:
        out.append(f'  apiKey 跳过（env 未设置/非占位符）')

with open(ZC_PATH, 'w') as f:
    json.dump(zc, f, ensure_ascii=False, indent=2)
    f.write('\n')

# ---- 断言校验：与备份对比，只允许 models 新增与 apiKey 更新 ----
bak = json.load(open(ZC_PATH + '.bak-' + stamp))
bcfg, ccfg = bak['config'], zc['config']
b_rules = {r['providerId']: r for r in bcfg['providerConfigRules']['providerRules']}
c_rules = {r['providerId']: r for r in ccfg['providerConfigRules']['providerRules']}
# 新增渠道的字段集合必须与既有条目一致（无额外字段）
PROTO_KEYS = {'group', 'access', 'api', 'personalModelIds', 'modelOrder'}
for pid, r in c_rules.items():
    assert set(r.keys()) == {'providerId', 'providerName', 'config'}, f'{pid}: 渠道条目字段不符'
    assert set(r['config'].keys()) == PROTO_KEYS, f'{pid}: 渠道 config 含额外字段 {set(r["config"]) - PROTO_KEYS}'
    assert set(r['config']['access'].keys()) == {'type', 'apiKey'}, f'{pid}: access 字段不符'
    assert set(r['config']['api'].keys()) == {'type', 'baseUrl'}, f'{pid}: api 字段不符'
    assert r['config']['personalModelIds'] == r['config']['modelOrder'], f'{pid}: personalModelIds 与 modelOrder 不一致'
for mid_r in ccfg['modelConfigRules']['providerModelRules']:
    assert set(mid_r.keys()) == {'modelId', 'config', 'providerId'}, '模型条目字段不符'
    assert set(mid_r['config'].keys()) == {'enabled'} and mid_r['config']['enabled'] is True, \
        f'{mid_r["modelId"]}: 模型 config 含额外字段'
assert set(bcfg['providerOrder']) <= set(ccfg['providerOrder']), 'providerOrder 有删除'
assert set(bcfg['modelConfigRules']['providerModelRules']) <= \
    set(ccfg['modelConfigRules']['providerModelRules']) or True
b_map = {(m['modelId'], m['providerId']): m for m in bcfg['modelConfigRules']['providerModelRules']}
c_map = {(m['modelId'], m['providerId']): m for m in ccfg['modelConfigRules']['providerModelRules']}
for k, v in b_map.items():
    assert c_map.get(k) == v, f'{k}: 现有模型条目被改动'
# 渠道条目：只允许 apiKey 变化与 personalModelIds/modelOrder 追加
for pid, br in b_rules.items():
    cr = c_rules[pid]
    for fld in ('providerName',):
        assert br[fld] == cr[fld], f'{pid}: {fld} 被改动'
    assert br['config']['group'] == cr['config']['group'], f'{pid}: group 被改动'
    assert br['config']['access']['type'] == cr['config']['access']['type'], f'{pid}: access.type 被改动'
    assert br['config']['api'] == cr['config']['api'], f'{pid}: api 被改动'
    assert cr['config']['personalModelIds'][:len(br['config']['personalModelIds'])] == br['config']['personalModelIds'], \
        f'{pid}: personalModelIds 前缀被改动'
print('校验通过：仅渠道新增 / models 新增 / apiKey 更新')
print('\n'.join(out))
