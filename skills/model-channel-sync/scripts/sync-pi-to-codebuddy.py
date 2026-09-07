#!/usr/bin/env python3
"""pi → CodeBuddy 同步（每渠道一个代表模型）。

用法:
    python3 scripts/sync-pi-to-codebuddy.py

CodeBuddy 配置 ~/.codebuddy/models.json 顶层为数组，每条目一个模型：
- url：openai 兼容模式，补全为 {baseUrl}/chat/completions（已含则不重复拼接）
- apiKey：从 pi 的 !echo -n "$VAR" 解析环境变量，写死实值（非占位符）
- 每渠道仅取一个代表模型（MODEL_INDEX 指定，默认 0 取第一个）
- 渠道匹配按 url host；pi 渠道无匹配条目时新增，codebuddy 中非 pi 渠道条目保留
幂等可重复执行；自动备份（.bak-YYYYMMDD）；断言校验；密钥不回显。
"""
import json, re, os, shutil, datetime
from urllib.parse import urlparse

PI_PATH = os.path.expanduser('~/.pi/agent/models.json')
WB_PATH = os.path.expanduser('~/.codebuddy/models.json')
MODEL_INDEX = 0  # 每个渠道取第几个模型作为代表
# 渠道 key → 显示名（用于 name 前缀，区分渠道）
CHANNEL_DISPLAY = {
    'sense': 'Sense', 'amd': 'AMD', 'ds2api': 'DS2API', 'newapi': 'NewAPI',
    'agnes': 'Agnes', 'cloudflare-workers-ai': 'Cloudflare Workers AI',
    'atomgit': 'AtomGit', 'kilo': 'Kilo', 'v2ex': 'V2EX', 'colab': 'Colab',
    'opencode': 'OpenCode', 'openrouter': 'OpenRouter', 'inferx': 'InferX',
}


def chat_url(base):
    """baseUrl → 补全 /chat/completions"""
    base = (base or '').rstrip('/')
    if base.endswith('/chat/completions'):
        return base
    return base + '/chat/completions'


def host_of(url):
    try:
        return urlparse(url or '').netloc
    except Exception:
        return ''


stamp = datetime.date.today().strftime('%Y%m%d')
shutil.copy(WB_PATH, WB_PATH + '.bak-' + stamp)
pi = json.load(open(PI_PATH))
wb = json.load(open(WB_PATH))

by_host = {}  # host → 代表条目（同一 host 取首个）
for entry in wb:
    h = host_of(entry.get('url', ''))
    if h and h not in by_host:
        by_host[h] = entry

out = []
for pname, pdata in pi['providers'].items():
    models = pdata.get('models', [])
    if not models:
        out.append(f'跳过 {pname}: pi 无模型（空列表）')
        continue
    base = pdata.get('baseUrl', '')
    if not base:
        out.append(f'跳过 {pname}: baseUrl 缺失')
        continue
    m = re.match(r'!echo -n "\$([A-Z0-9_]+)"', pdata.get('apiKey', ''))
    if not (m and os.environ.get(m.group(1))):
        out.append(f'跳过 {pname}: apiKey env 未设置/非占位符')
        continue
    key_val = os.environ[m.group(1)]
    rep = models[MODEL_INDEX]
    url = chat_url(base)
    disp = CHANNEL_DISPLAY.get(pname, pname)
    mname = rep.get('name', rep['id'])
    # 模型名已含渠道前缀则不再重复拼接（如 amd 的 "AMD DeepSeek V4 Flash"）
    entry_name = mname if mname.startswith(disp) else f'{disp} {mname}'
    entry = by_host.get(host_of(base))
    if entry is None:
        wb.append({
            'id': rep['id'],
            'name': entry_name,
            'vendor': 'Custom',
            'url': url,
            'apiKey': key_val,
            'supportsToolCall': True,
            'supportsImages': False,
            'supportsReasoning': False,
            'useCustomProtocol': False,
        })
        out.append(f'{pname}: 新增条目（{rep["id"]}）')
    else:
        changed = []
        for field, val in (('url', url), ('apiKey', key_val),
                           ('id', rep['id']), ('name', entry_name)):
            if entry.get(field) != val:
                entry[field] = val
                changed.append(field)
        out.append(f'{pname}: 更新条目 {changed if changed else "无变化"}（{rep["id"]}）')

with open(WB_PATH, 'w') as f:
    json.dump(wb, f, ensure_ascii=False, indent=2)
    f.write('\n')

bak = json.load(open(WB_PATH + '.bak-' + stamp))
assert len(wb) >= len(bak), '条目数减少'
for e in wb:
    assert e['url'].endswith('/chat/completions'), f"{e['id']}: url 未补全 chat/completions"
    assert not e['apiKey'].startswith(('!echo', '{env:')), f"{e['id']}: apiKey 仍是占位符"
print('校验通过：条目数不减少，url 补全 chat/completions，apiKey 为实值')
print('\n'.join(out))