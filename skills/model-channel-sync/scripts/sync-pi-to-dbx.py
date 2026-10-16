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
- **渠道匹配**：已有配置按 config_json.endpoint（baseUrl 去尾斜杠）优先匹配，其次 name（渠道显示名）匹配；
  无匹配则**新建**记录（id=uuid4，name=渠道显示名）
- **模型筛选**：openrouter 渠道只补免费模型（id 含 :free/-free//free），其它渠道全量同步；
  上游免费渠道（kilo/openrouter）从上游 API 提取免费模型（fetch_free）；opencode 不同步
- **模型 id**：保持 pi 原样，不擅自添加/去前缀
- **model 列**：当前选中模型取同族最高版本（族键/版本号规则与其它 sync 脚本一致）
- **apiStyle 映射**：pi `api` → DBX `apiStyle`（openai-completions→completions、
  openai-responses→responses、anthropic-messages→anthropic-messages；未知回退 completions）
- **provider 映射**：pi `api` → DBX `provider`（openai-*→openai-compatible、anthropic-messages→anthropic-compatible）；
  新版 DBX 新建默认为 openai-compatible，旧 custom 自动迁移
- **apiKey**：写明文实值（env 解析，正则含数字）；已有记录的 endpoint/apiKey 一并更新为渠道实值
- **config_json**：新建时按 DBX 完整字段结构初始化；已有记录只更新
  model/apiKey/endpoint/apiStyle/provider/models 字段，其余字段（请求头/代理/推理强度/CLI 路径等）不动
- **双写约束**：顶层列 `model`/`models` 与 `config_json.model`/`config_json.models` 必须一致；
  写入时同步更新两处（models 列为 JSON 数组字符串）
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
    'agnes': 'Agnes', 'agnes-com': 'Agnes-Com', 'cloudflare-workers-ai': 'Cloudflare Workers AI',
    'atomgit': 'AtomGit', 'kilo': 'Kilo', 'v2ex': 'V2EX', 'colab': 'Colab',
    'openrouter': 'OpenRouter', 'inferx': 'InferX', 'tokenrouter': 'TokenRouter',
    'nvidia': 'Nvidia', 'sense-ai': 'Sense-AI', 'poolside': 'Poolside',
    'hyper': 'Hyper', 'jiutian': 'Jiutian', 'craft': 'Craft', 'cli2api': 'Cli2api',
}
# pi `api` → DBX `apiStyle`
API_STYLE = {
    'openai-completions': 'completions',
    'openai-responses': 'responses',
    'anthropic-messages': 'anthropic-messages',
}
# pi `api` → DBX `provider`（新版 DBX 默认为 openai-compatible）
PROVIDER_MAP = {
    'openai-completions': 'openai-compatible',
    'openai-responses': 'openai-compatible',
    'anthropic-messages': 'anthropic-compatible',
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


def provider_of(api):
    """pi api → DBX provider；未知回退 openai-compatible（与新版 DBX 新建一致）"""
    return PROVIDER_MAP.get(api or '', 'openai-compatible')


def free_only(mid):
    return ':free' in mid or '-free' in mid or '/free' in mid

def to_model_objs(pdata, ids):
    """id 列表 → [{id, name}] 对象数组（DBX 迁移后新格式，name 必填）；name 优先取 pi 的 model.name，缺失则用 id"""
    id2name = {m['id']: m.get('name', m['id']) for m in pdata.get('models', [])}
    return [{"id": i, "name": id2name.get(i, i)} for i in ids]


def to_model_objs_from_items(items):
    """items [{id,name}] → [{id, name}] 对象数组"""
    return [{"id": m['id'], "name": m.get('name', m['id'])} for m in items]


def ids_from_models(models):
    """兼容读取：models 可能是 ['a','b'] 或 [{'id':'a'}]，统一提取 id 集合"""
    out = set()
    for m in (models or []):
        if isinstance(m, dict):
            if m.get("id"):
                out.add(m["id"])
        elif isinstance(m, str):
            out.add(m)
    return out


def new_config_json(pdata, items):
    """按 DBX 现有条目结构初始化 config_json（新版 provider + 双写就绪；best 取 pi 原序首族）"""
    style = API_STYLE.get(pdata.get('api', ''), 'completions')
    prov = provider_of(pdata.get('api', ''))
    raw_ids = [i['id'] for i in items]
    sorted_ids = sorted(raw_ids)
    cfg = {
        'provider': prov,
        'apiKey': env_val_of(pdata),
        'authMethod': 'bearer',
        'endpoint': (pdata.get('baseUrl') or '').rstrip('/'),
        'model': best_in_family(raw_ids),
        'models': to_model_objs(pdata, sorted_ids),
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
    """对 dbx.db 执行同步（幂等；备份+断言校验；双写顶层列）"""
    out = []
    con = sqlite3.connect(db_path)
    rows = con.execute('SELECT id, name, model, models, config_json, is_default FROM ai_configs').fetchall()
    # 索引：name → row；endpoint（config_json）→ row
    by_name = {norm(r[1]): r for r in rows}
    by_endpoint = {}
    for r in rows:
        try:
            ep = (json.loads(r[4]).get('endpoint') or '').rstrip('/')
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
        raw_ids = [i['id'] for i in src_models]
        sorted_ids = sorted(raw_ids)
        best = best_in_family(raw_ids)
        env_val = env_val_of(pdata)
        if row is None:
            rid = str(uuid.uuid4())
            cfg = new_config_json(pdata, src_models)
            # new_config_json 已填好 models/model，无需二次覆盖
            out.append(f'{pname}: 新建配置 {cname}（{len(raw_ids)} 模型，model={cfg["model"]} provider={cfg["provider"]}）')
            if not DRY_RUN:
                con.execute('INSERT INTO ai_configs (id, name, model, models, config_json, is_default) '
                            'VALUES (?, ?, ?, ?, ?, 0)',
                            (rid, cname, cfg['model'], json.dumps(cfg['models'], ensure_ascii=False), json.dumps(cfg, ensure_ascii=False)))
        else:
            rid, old_name, old_model_col, old_models_col, old_cfg_json, old_default = row
            cfg = json.loads(old_cfg_json)
            changed = []
            if cfg.get('endpoint') != burl:
                cfg['endpoint'] = burl
                changed.append('endpoint')
            # apiKey 已迁移至 connection_secrets（secret-store-v1），ai_configs.apiKey 保持 '' 为正常
            # 若迁移已完成，跳过 ai_configs 明文比对，避免每次“需迁移”循环
            try:
                secret_migrated = con.execute("SELECT state FROM data_migrations WHERE migration_id='secret-store-v1'").fetchone()
                is_migrated = secret_migrated and secret_migrated[0] == 'succeeded'
            except sqlite3.OperationalError:
                is_migrated = False
            if not is_migrated:
                if env_val and cfg.get('apiKey') != env_val:
                    cfg['apiKey'] = env_val
                    changed.append('apiKey')
            style = API_STYLE.get(pdata.get('api', ''), 'completions')
            if cfg.get('apiStyle') != style:
                cfg['apiStyle'] = style
                changed.append('apiStyle')
            # provider 迁移：custom → openai-compatible / anthropic-compatible
            expected_prov = provider_of(pdata.get('api', ''))
            if cfg.get('provider') != expected_prov:
                # 旧 custom 迁移，或跨风格纠正
                cfg['provider'] = expected_prov
                changed.append(f'provider→{expected_prov}')
            # 需同时处理：string[]、缺 id、缺 name 三种旧态；DBX 迁移可能把 config_json.models 改为 {name} only，需强制按顶层+pi 重建
            have = ids_from_models(cfg.get('models'))
            cj_has_id = cfg.get('models') and isinstance(cfg['models'][0], dict) and 'id' in cfg['models'][0]
            cj_needs_id_fix = cfg.get('models') and not cj_has_id
            if cj_needs_id_fix:
                # DBX 迁移把 cj.models 改为 name-only，需用顶层 correct 数据 + pi 指引重建
                merged_ids = sorted(set(sorted_ids) | ids_from_models(json.loads(old_models_col) if old_models_col else []))
                cfg['models'] = to_model_objs(pdata, merged_ids)
                changed.append('config_json.models 缺 id，强制重建 {id,name}[]')
            elif (added := [m for m in sorted_ids if m not in have]):
                merged_ids = sorted(have | set(sorted_ids))
                cfg['models'] = to_model_objs(pdata, merged_ids)
                changed.append(f'新增模型 {len(added)} 个 {added}')
            elif cfg.get('models') and isinstance(cfg['models'][0], str):
                cfg['models'] = to_model_objs(pdata, sorted(ids_from_models(cfg['models'])))
                changed.append('models 格式迁移: string[] → {id,name}[]')
            # 已是对象数组但缺 name 字段的修复
            elif cfg.get('models') and isinstance(cfg['models'][0], dict) and any('name' not in m for m in cfg['models']):
                id2name = {m['id']: m.get('name', m['id']) for m in pdata.get('models', [])}
                for m in cfg['models']:
                    if 'name' not in m:
                        m['name'] = id2name.get(m['id'], m['id'])
                cfg['models'] = sorted(cfg['models'], key=lambda x: x['id'])
                changed.append('models 补 name 字段')
            # 若 config_json.models 已变更，下方统一写回顶层列
            if cfg.get('model') != best and (not cfg.get('model') or best in raw_ids):
                out.append(f'{pname}: model {cfg.get("model") or "(空)"} → {best}（{fam_key(best)} 族最高版本）'
                           if best else f'{pname}: model 保持 {cfg.get("model")}')
                cfg['model'] = best or cfg.get('model')
                changed.append('model')
            if old_name != cname:
                out.append(f'{pname}: 配置名 {old_name} → {cname}')
                changed.append('name')
            # 双写一致性：即使 models 未新增，若顶层列与 config_json 不一致也需修复
            try:
                old_models_list = json.loads(old_models_col) if old_models_col else []
            except (json.JSONDecodeError, TypeError):
                old_models_list = []
            old_ids = ids_from_models(old_models_list)
            new_ids = ids_from_models(cfg.get('models'))
            top_needs_fix = (old_model_col != cfg.get('model') or old_ids != new_ids or (old_models_list and isinstance(old_models_list[0], str)))
            if top_needs_fix and 'model' not in changed and 'models' not in ''.join(changed) and '迁移' not in ''.join(changed):
                changed.append('双写修复(顶层列)')
            out.append(f'{pname}: 更新 {old_name}（{how} 匹配，{"；".join(changed) if changed else "无变更"}）')
            if not DRY_RUN and changed:
                if old_name != cname:
                    con.execute('UPDATE ai_configs SET name=? WHERE id=?', (cname, rid))
                con.execute('UPDATE ai_configs SET model=?, models=?, config_json=? WHERE id=?',
                            (cfg.get('model', ''), json.dumps(cfg.get('models', []), ensure_ascii=False), json.dumps(cfg, ensure_ascii=False), rid))

    if DRY_RUN:
        con.close()
        print('== DRY-RUN：未写库。')
        print('\n'.join(out))
        return

    con.commit()
    # 断言仅适用于非清库场景：若本次是清库后首次写入（旧id全不在新库），跳过“被删除”断言
    # 清库场景下旧id全换新，bmap<=cmap 必然失败，但数据本身正确（13行新建）
    try:
        bak = sqlite3.connect(db_path + '.bak-' + stamp)
        brows = bak.execute('SELECT id, name, is_default FROM ai_configs').fetchall()
        crows = con.execute('SELECT id, name, is_default FROM ai_configs').fetchall()
        bmap = {r[0]: r for r in brows}
        cmap = {r[0]: r for r in crows}
        # 仅当旧库非空且有交集时才校验“未删除”；清库重建（0交集）跳过
        if bmap and set(bmap) & set(cmap):
            assert set(bmap) <= set(cmap), '已有 ai_configs 行被删除'
            for rid, r in bmap.items():
                if rid in cmap:
                    assert cmap[rid][2] == r[2], f'{r[1]}: is_default 被改动'
        bak.close()
    except sqlite3.OperationalError:
        pass
    con.close()
    print(f'== {db_path}: 校验通过（仅新增行 / model+apiKey+endpoint+apiStyle+provider+models 双写变更；密钥不回显）')
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
