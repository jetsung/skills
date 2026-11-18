#!/usr/bin/env python3
"""pi → atomcode 全量同步（新式「账号 + 模型剖面」结构，只增不删）。

用法:
    python3 scripts/sync-pi-to-atomcode.py

目标配置: ~/.atomcode/config.toml（TOML，两套结构并存）:
- 旧式 [providers.<名>]: ProviderConfig，type/api_key/model/base_url/context_window 全在一块
- 新式（v5.0.7+，本脚本使用）:
    [provider_accounts.<账号id>]  provider = "<preset id>" / "openai-compatible" / "anthropic-compatible"
                                  base_url = "https://.../v1"   api_key = "$VAR"
    [models."<账号id>/<模型id>"]  account = "<账号id>"  model = "<wire 模型名>"
                                  display_name / context_window / supports_vision
  selection id（models 表的 key）推荐 <account>/<model>，实际是任意字符串；
  既有配置里 Sense/glm-5.2 与 AtomGit-glm5.3-flash 两种写法都能解析，
  因此匹配现有条目按 (account, model) 而非 key 字面量。

字段映射（pi → atomcode）:
| pi 字段                 | atomcode 字段                        |
|-------------------------|--------------------------------------|
| providers.<渠道>.baseUrl| provider_accounts.<ACC>.base_url     |
| providers.<渠道>.api    | provider（openai-completions→openai-compatible，anthropic*→anthropic-compatible）|
| providers.<渠道>.apiKey !echo -n "$VAR" → api_key = "$VAR"（不落明文密钥）|
| models[].id             | models[].model + selection key 后缀  |
| models[].name           | display_name                         |
| models[].contextWindow  | context_window（缺省 128000）        |
| models[].input 含 image | supports_vision = true               |

规则:
- 仅同步文本聊天模型：classifier（决策模型，仅 pi）与非文本输出（image/video）由
  pi_cache.filter_models 剔除，atomcode 无对应概念
- 渠道匹配：base_url 去尾斜杠强绑定 → 账号 id 规范化名 + ALIAS；命中则复用，未命中新建
- 禁止自动新建的渠道（pi_cache.no_auto_add：opencode/openrouter）跳过
- 模型匹配：同 (account, model) 已存在则不动（既有字段可能是用户手改，不覆盖）
- 不改动 default_provider / default_model / vision_preprocessor_provider
- 写入为文本级追加（环境无 TOML 写入库），保留原文件全部内容与注释；自动备份 + 断言校验
- 密钥不回显（只报告 env 变量名）
"""
import os, re, shutil, sys, tomllib, datetime

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pi_cache

AC_PATH = os.environ.get('ATOMCODE_CONFIG') or os.path.expanduser('~/.atomcode/config.toml')
ALIAS = {'cloudflare-workers-ai': 'Cloudflare', 'amd': 'AMD', 'nvidia': 'NVIDIA'}
# 不同步的渠道（上游价格数据不正确等）
SKIP_CHANNELS = ('opencode',)
DEFAULT_CONTEXT_WINDOW = 128000
API_MAP = {'openai-completions': 'openai-compatible', 'openai-responses': 'openai-responses',
           'anthropic': 'anthropic-compatible', 'anthropic-messages': 'anthropic-compatible'}


def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def account_id(pname):
    """渠道名 → 账号 id（与本机既有 Sense/AtomGit 风格一致：分段首字母大写）。"""
    name = ALIAS.get(pname, pname)
    return ''.join(w[:1].upper() + w[1:] for w in re.split(r'[-_]', name) if w)


def env_var_of(api_key_str):
    """pi 的 !echo -n "$VAR" → VAR；其它形式返回 None。"""
    m = re.search(r'!echo -n "\$([A-Z0-9_]+)"', api_key_str or '')
    return m.group(1) if m else None


def q(s):
    """TOML 基本字符串字面量。"""
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def vision(m):
    inp = m.get('input') or []
    return 'image' in inp or bool(re.search(r'vl|vision|visual', m.get('id', ''), re.I))


def toml_tables(text, table):
    """返回 {表名: 起始行号}，table 形如 provider_accounts / models。"""
    out, pat = {}, re.compile(r'^\[' + table + r'\.("([^"]*)"|([^\]\s]+))\]\s*$')
    for i, line in enumerate(text.splitlines()):
        m = pat.match(line)
        if m:
            out[m.group(2) or m.group(3)] = i
    return out


stamp = datetime.date.today().strftime('%Y%m%d')
shutil.copy(AC_PATH, AC_PATH + '.bak-' + stamp)
raw = open(AC_PATH, encoding='utf-8').read()
cfg = tomllib.loads(raw)
accounts = dict(cfg.get('provider_accounts') or {})
models = dict(cfg.get('models') or {})
# 既有 (account, wire model) → selection key，避免同一模型因 key 写法不同被重复添加
existing = {}
for key, mv in models.items():
    existing.setdefault((mv.get('account'), mv.get('model')), key)
acc_by_norm = {norm(k): k for k in accounts}
acc_by_url = {(v.get('base_url') or '').rstrip('/'): k for k, v in accounts.items()}

out, blocks = [], []
pi = pi_cache.load()
for pname, pdata in pi['providers'].items():
    if pname in SKIP_CHANNELS:
        out.append(f'跳过 {pname}: 不同步')
        continue
    items, dropped = pi_cache.filter_models(pi, pname, pdata.get('models', []))
    note = pi_cache.dropped_note(pname, dropped)
    if note:
        out.append(note)
    if not items:
        out.append(f'跳过 {pname}: 无文本聊天模型')
        continue
    base_url = (pdata.get('baseUrl') or '').rstrip('/')
    api_kind = API_MAP.get(pdata.get('api', ''), 'openai-compatible')
    acc = acc_by_url.get(base_url) or acc_by_norm.get(norm(account_id(pname)))
    if acc is None and pi_cache.no_auto_add(pname):
        out.append(f'跳过 {pname}: 禁止自动新建账号（opencode/openrouter 需显式声明）')
        continue
    if acc is None:
        acc = account_id(pname)
        while norm(acc) in acc_by_norm:
            acc = acc + '-'
        var = env_var_of(pdata.get('apiKey'))
        blk = [f'[provider_accounts.{q(acc) if "." in acc or " " in acc else acc}]',
               f'provider = {q(api_kind)}', f'base_url = {q(base_url)}']
        if var:
            blk.append(f'api_key = {q("$" + var)}')
        blocks += blk + ['']
        out.append(f'{pname}: 新建账号 {acc}（{api_kind}, {base_url}, '
                   f'{"api_key: $" + var if var else "api_key 待补（env 未设置/非占位符）"}）')
        acc_by_norm[norm(acc)] = acc
        acc_by_url[base_url] = acc
    else:
        out.append(f'{pname}: 复用账号 {acc}')

    added = []
    for m in items:
        mid = m['id']
        if (acc, mid) in existing:
            continue
        key = f'{acc}/{mid}'
        n, blk_key = 2, key
        while blk_key in models:
            blk_key = f'{key}-{n}'
            n += 1
        lines = [f'[models.{q(blk_key)}]', f'account = {q(acc)}', f'model = {q(mid)}']
        if m.get('name'):
            lines.append(f'display_name = {q(m["name"])}')
        lines.append(f'context_window = {m.get("contextWindow") or DEFAULT_CONTEXT_WINDOW}')
        if vision(m):
            lines.append('supports_vision = true')
        blocks += lines + ['']
        models[blk_key] = {'account': acc, 'model': mid}
        existing[(acc, mid)] = blk_key
        acc_by_norm[norm(acc)] = acc
        added.append(mid)
    out.append(f'  {pname}: 新增模型 {len(added)} 个 {added if added else ""}')

if blocks:
    text = raw.rstrip('\n') + '\n\n' + '\n'.join(blocks).rstrip('\n') + '\n'
    open(AC_PATH, 'w', encoding='utf-8').write(text)

# ---- 断言校验：既有内容逐字保留，只允许新增账号段与模型段 ----
new = tomllib.load(open(AC_PATH, 'rb'))
assert open(AC_PATH, encoding='utf-8').read().startswith(raw.rstrip('\n')), '原文件内容被改动'
for k, v in (cfg.get('provider_accounts') or {}).items():
    assert new['provider_accounts'][k] == v, f'账号 {k} 被改动'
for k, v in (cfg.get('models') or {}).items():
    assert new['models'][k] == v, f'模型 {k} 被改动'
for fld in ('default_provider', 'default_model', 'vision_preprocessor_provider'):
    assert cfg.get(fld) == new.get(fld), f'{fld} 被改动'
assert set(cfg.keys()) <= set(new.keys()), '顶层表被删除'
print('校验通过：仅新增 provider_accounts / models 段')
print('\n'.join(out))
