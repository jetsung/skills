#!/usr/bin/env python3
"""pi → DBX (ai_configs 表) 全量同步（每渠道一条命名 AI 配置）。

用法:
    python3 scripts/sync-pi-to-dbx.py            # 实际写入
    python3 scripts/sync-pi-to-dbx.py --dry-run  # 只打印计划，不写库

目标：DBX 桌面端数据目录下的 SQLite 库 `dbx.db` 的 `ai_configs` 表
（表结构见 references/dbx.md；每条记录 = 一个命名 AI 配置，config_json 为 JSON 字符串）。

数据目录优先级：DBX_DATA_DIR 环境变量 → ~/.local/share/com.dbx.app（Linux）→
~/Library/Application Support/com.dbx.app（macOS）→ %APPDATA%/com.dbx.app（Windows）。

规则：
- **渠道匹配**：已有配置按 name（渠道显示名）或 config_json.endpoint（baseUrl 去尾斜杠）匹配；
  无匹配则**新建**记录（id=uuid4，name=渠道显示名）
- **模型筛选**：openrouter 渠道只补免费模型（id 含 :free/-free//free），其它渠道全量同步；
  上游免费渠道（kilo/openrouter）从上游 API 提取免费模型（fetch_free）；opencode 不同步
- **模型 id**：保持 pi 原样，不擅自添加/去前缀
- **model 列**：当前选中模型取同族最高版本（族键/版本号规则与其它 sync 脚本一致）
- **apiStyle 映射**：pi `api` → DBX `apiStyle`（openai-completions→completions、
  openai-responses→responses、anthropic-messages→anthropic-messages；未知回退 completions）
- **apiKey**：写明文实值（env 解析，正则含数字）；已有记录的 endpoint/apiKey 一并更新为渠道实值
- **config_json**：新建时按 DBX 完整字段结构初始化；已有记录只更新
  model/apiKey/endpoint/apiStyle/models 字段，其余字段（请求头/代理/推理强度/CLI 路径等）不动
- **is_default**：不改动已有值；新建记录写 0（用户可在 DBX 设置中手动指定默认）
幂等可重复执行；写库前备份（.bak-YYYYMMDD）并断言校验；密钥不回显。
"""
import json, re, os, shutil, datetime, uuid, sys, sqlite3

sys.dont_write_bytecode = True  # 不生成 __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pi_cache
import fetch_free

DRY_RUN = '--dry-run' in sys.argv

# 数据目录定位（与 DBX 文档一致：DBX_DATA_DIR 指向包含 dbx.db 的目录）
DBX_DATA_DIR = os.environ.get('DBX_DATA_DIR') or next(
    (d for d in ('~/.local/share/com.dbx.app',
                 '~/Library/Application Support/com.dbx.app',
                 os.path.join(os.environ.get('APPDATA', ''), 'com.dbx.app'))
     if d and os.path.isfile(os.path.expanduser(os.path.join(d, 'dbx.db')))), None)

# kilo/openrouter 渠道不走 pi models 基准，改从上游 API 提取免费模型；opencode 不同步
UPSTREAM_FREE = ('kilo', 'openrouter')
SKIP_CHANNELS = ('opencode',)
# 免费渠道：这些渠道只同步免费模型（id 含 :free/-free//free）
FREE_CHANNELS = ('openrouter',)
# 渠道 key → 配置名称（= ai_configs.name，也是 DBX 中显示的配置名）
CHANNEL_DISPLAY = {
    'sense': 'Sense', 'amd': 'AMD', 'ds2api': 'DS2API', 'newapi': 'NewAPI',
    'agnes': 'Agnes', 'cloudflare-workers-ai': 'Cloudflare Workers AI',
    'atomgit': 'AtomGit', 'kilo': 'Kilo', 'v2ex': 'V2EX', 'colab': 'Colab',
    'opencode': 'OpenCode', 'openrouter': 'OpenRouter', 'inferx': 'InferX',
    'tokenrouter': 'TokenRouter',
}
# pi `api` → DBX `apiStyle`
API_STYLE = {
    'openai-completions': 'completions',
    'openai-responses': 'responses',
    'anthropic-messages': 'anthropic-messages',
}
# 新建记录时 config_json 的固定/兜底字段（与 DBX 现有条目结构一致，见 references/dbx.md）
CLI_KEYS = ('codex', 'claudeCode', 'piAgent', 'opencode', 'cursor', 'grok',
            'codebuddy', 'qoder')


def norm(s):
    return (s or '').strip().lower()


def fam_key(mid):
    """族键：最后一个 / 后的段小写后的开头连续字母（^[a-z]+，提取不到用整段）"""
    seg = mid.rsplit('/', 1)[-1].lower()
    m = re.match(r'^[a-z]+', seg)
    return m.group(0) if m else seg


def ver_key(mid):
    """版本号：该段首个数字串，如 agnes-2.5-flash → (2, 5)；无数字 → ()"""
    seg = mid.rsplit('/', 1)[-1].lower()
    m = re.search(r'\d+(?:\.\d+)*', seg)
    return tuple(int(x) for x in m.group(0).split('.')) if m else ()


def best_in_family(ids):
    """同族最高版本的模型 id；无模型返回 ''。族按首个模型的族键判定。"""
    if not ids:
        return ''
    fam = fam_key(ids[0])
    return max((i for i in ids if fam_key(i) == fam), key=ver_key)


def env_val_of(pdata):
    """pi apiKey 占位符 `!echo -n "$VAR"` → env 实值；未设置返回 ''"""
    m = re.match(r'!echo -n "\$([A-Z0-9_]+)"', pdata.get('apiKey', ''))
    return os.environ[m.group(1)] if (m and os.environ.get(m.group(1))) else ''


def free_only(mid):
    return ':free' in mid or '-free' in mid or '/free' in mid


def new_config_json(pdata, items):
    """按 DBX 现有条目结构初始化 config_json"""
    style = API_STYLE.get(pdata.get('api', ''), 'completions')
    cfg = {
        'provider': 'custom',
        'apiKey': env_val_of(pdata),
        'authMethod': 'bearer',
        'endpoint': (pdata.get('baseUrl') or '').rstrip('/'),
        'model': best_in_family([i['id'] for i in items]),
        'models': [],
        'apiStyle': style,
        'customHeaders': {},
        'proxyEnabled': False,
        'proxyUrl': '',
        'skipTlsVerify': False,
        'enableThinking': True,
        'reasoningLevel': 'default',
        'maxOutputTokens': None,
        'contextWindow': None,
        'maxRetries': None,
    }
    for k in CLI_KEYS:
        cfg[k + 'CliPath'] = None
        cfg[k + 'CliEnv'] = {}
    return cfg


def sync(db_path, pi):
    """对 dbx.db 执行同步（幂等；备份+断言校验）"""
    out = []
    con = sqlite3.connect(db_path)
    rows = con.execute('SELECT id, name, model, config_json, is_default FROM ai_configs').fetchall()
    # 索引：name → row；endpoint（config_json）→ row
    by_name = {norm(r[1]): r for r in rows}
    by_endpoint = {}
    for r in rows:
        try:
            ep = (json.loads(r[3]).get('endpoint') or '').rstrip('/')
        except (json.JSONDecodeError, AttributeError):
            ep = ''
        if ep:
            by_endpoint.setdefault(ep, r)

    if not DRY_RUN:
        stamp = datetime.date.today().strftime('%Y%m%d')
        shutil.copy(db_path, db_path + '.bak-' + stamp)

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
            src_models, dropped = pi_cache.filter_models(pi, pname, pdata.get('models', []))
            if dropped:
                out.append(f'{pname}: 剔除失效模型 {dropped}（实时 /models 不再存在）')
        if pname in FREE_CHANNELS:
            src_models = [i for i in src_models if free_only(i['id'])]
        if not src_models:
            out.append(f'跳过 {pname}: 无模型（空列表，或免费过滤后为空）')
            continue

        cname = CHANNEL_DISPLAY.get(pname, pname)
        burl = (pdata.get('baseUrl') or '').rstrip('/')
        # 1) endpoint 匹配（去尾斜杠，唯一绑定）→ 2) name 匹配 → 3) 新建
        row = by_endpoint.get(burl) if burl else None
        how = 'endpoint'
        if row is None:
            row = by_name.get(norm(cname))
            how = 'name'
        model_ids = [i['id'] for i in src_models]
        best = best_in_family(model_ids)
        env_val = env_val_of(pdata)
        if row is None:
            rid = str(uuid.uuid4())
            cfg = new_config_json(pdata, src_models)
            cfg['model'] = best
            out.append(f'{pname}: 新建配置 {cname}（{len(model_ids)} 模型，model={best}）')
            if not DRY_RUN:
                con.execute('INSERT INTO ai_configs (id, name, model, models, config_json, is_default) '
                            'VALUES (?, ?, ?, ?, ?, 0)',
                            (rid, cname, best, '[]', json.dumps(cfg, ensure_ascii=False)))
        else:
            rid, old_name, old_model, old_cfg_json, old_default = row
            cfg = json.loads(old_cfg_json)
            changed = []
            if cfg.get('endpoint') != burl:
                cfg['endpoint'] = burl
                changed.append('endpoint')
            if env_val and cfg.get('apiKey') != env_val:
                cfg['apiKey'] = env_val
                changed.append('apiKey')
            style = API_STYLE.get(pdata.get('api', ''), 'completions')
            if cfg.get('apiStyle') != style:
                cfg['apiStyle'] = style
                changed.append('apiStyle')
            # 模型列表只增不删（合并式）；已有条目不动
            have = set(cfg.get('models') or [])
            added = [m for m in model_ids if m not in have]
            if added:
                cfg['models'] = sorted((cfg.get('models') or []) + model_ids)
                changed.append(f'新增模型 {len(added)} 个 {added}')
            if cfg.get('model') != best and (not cfg.get('model') or best in model_ids):
                out.append(f'{pname}: model {cfg.get("model") or "(空)"} → {best}（{fam_key(best)} 族最高版本）'
                           if best else f'{pname}: model 保持 {cfg.get("model")}')
                cfg['model'] = best or cfg.get('model')
                changed.append('model')
            if old_name != cname:
                out.append(f'{pname}: 配置名 {old_name} → {cname}')
                changed.append('name')
            out.append(f'{pname}: 更新 {old_name}（{how} 匹配，{"；".join(changed) if changed else "无变更"}）')
            if not DRY_RUN and changed:
                if old_name != cname:
                    con.execute('UPDATE ai_configs SET name=? WHERE id=?', (cname, rid))
                con.execute('UPDATE ai_configs SET model=?, config_json=? WHERE id=?',
                            (cfg.get('model', ''), json.dumps(cfg, ensure_ascii=False), rid))

    if DRY_RUN:
        con.close()
        print('== DRY-RUN：未写库。')
        print('\n'.join(out))
        return

    con.commit()
    bak = sqlite3.connect(db_path + '.bak-' + stamp)
    # 断言：行数只增不减；已有行的 id/is_default 不变；name 改动仅限 endpoint 匹配的规范化
    brows = bak.execute('SELECT id, name, is_default FROM ai_configs').fetchall()
    crows = con.execute('SELECT id, name, is_default FROM ai_configs').fetchall()
    bmap = {r[0]: r for r in brows}
    cmap = {r[0]: r for r in crows}
    assert set(bmap) <= set(cmap), '已有 ai_configs 行被删除'
    for rid, r in bmap.items():
        assert cmap[rid][2] == r[2], f'{r[1]}: is_default 被改动'
    bak.close()
    con.close()
    print(f'== {db_path}: 校验通过（仅新增行 / model+apiKey+endpoint+apiStyle+models 变更；密钥不回显）')
    print('\n'.join(out))


def main():
    if not DBX_DATA_DIR:
        raise SystemExit('错误：未找到 DBX 数据目录（dbx.db）；可设置 DBX_DATA_DIR 指向包含 dbx.db 的目录')
    db_path = os.path.expanduser(os.path.join(DBX_DATA_DIR, 'dbx.db'))
    print(f'同步目标: {db_path}（ai_configs 表）' + ('  [DRY-RUN]' if DRY_RUN else ''))
    pi = pi_cache.load()
    sync(db_path, pi)


if __name__ == '__main__':
    main()
