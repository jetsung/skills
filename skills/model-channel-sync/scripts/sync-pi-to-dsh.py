#!/usr/bin/env python3
"""pi → dsh 同步（合并式：保留现有 + 补 pi 缺失模型）。

用法:
    python3 scripts/sync-pi-to-dsh.py [--profile web] [--dry-run]

配置位置与结构（dsh 已升级为 Cordis patch 层）：
    $DSH_HOME/profiles/<profile>/cordis.patch.yml
  - 顶层是 **数组**，每项 {id, name?, config}；providers 位于 id == 'llm-pi-ai' 条目的
    config.providers 下（不再是旧的 settings.yaml 映射式 llm-pi-ai.providers）
  - 渠道字段：displayName / apiKeyEnv / api / baseURL / models（baseURL 全大写）
  - models 元素只含 id（可选 input 等，见 references/dsh.md）

写入方式：**文本级增量插入**——先用 PyYAML 解析做判断，再把缺失的 `- id: xxx` 行插到对应
provider 的 models 段末尾，保留原文件注释、缩进与条目顺序。该文件是 patch 列表，含文件头
注释与 ui-settings-general / agent-default-model / web-search-deepseek 等无关条目，
**不可用 yaml.safe_dump 整篇重写**。

密钥：provider 只用 apiKeyEnv（环境变量名引用），明文存 $DSH_HOME/.credentials.yaml，
patch 内不落明文。本脚本只读写 models，apiKeyEnv 原样保留，不读取也不写入任何密钥值。
幂等（无变更不写文件）；自动备份（.bak-YYYYMMDD）；断言校验只允许 models 新增。
"""
import re, os, shutil, datetime, sys
import yaml

sys.dont_write_bytecode = True  # 不生成 __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pi_cache
import fetch_free

DSH_HOME = os.environ.get('DSH_HOME') or os.path.expanduser('~/.dsh')
DEFAULT_PROFILE = os.environ.get('DSH_PROFILE') or 'web'
LLM_ENTRY_ID = 'llm-pi-ai'
ALIAS = {}  # 渠道别名映射（dsh key ≠ pi key 时在此登记）
# kilo/openrouter 渠道不走 pi models 基准，改从上游 API 提取免费模型（含价格 0，剔除图像/视频类）；
# opencode 渠道不同步（上游价格数据不正确）
UPSTREAM_FREE = ('kilo', 'openrouter')
SKIP_CHANNELS = ('opencode',)

TOP_RE = re.compile(r'^-\s+id:\s*(\S+)\s*$')


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def parse_args(argv):
    profile, dry = DEFAULT_PROFILE, False
    it = iter(argv)
    for a in it:
        if a == '--profile':
            profile = next(it)
        elif a.startswith('--profile='):
            profile = a.split('=', 1)[1]
        elif a == '--dry-run':
            dry = True
        else:
            raise SystemExit(f'未知参数: {a}')
    return profile, dry


# ---------- 文本层：定位与插入（保留原文件格式） ----------

def _indent(line):
    return len(line) - len(line.lstrip())


def entry_bounds(lines, eid):
    """返回顶层 patch 条目 `- id: <eid>` 的行范围 (start, end)。"""
    start = None
    for i, line in enumerate(lines):
        m = TOP_RE.match(line)
        if m and m.group(1).strip('\'"') == eid:
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if TOP_RE.match(lines[j]):
            end = j
            break
    return start, end


def find_key_line(lines, lo, hi, indent, key):
    """在 [lo, hi) 内查找缩进恰为 indent 的 `key:` 行。"""
    pat = re.compile(r'^\s{%d}%s\s*:' % (indent, re.escape(key)))
    for i in range(lo, hi):
        if pat.match(lines[i]):
            return i
    return None


def block_bounds(lines, lo, hi, indent):
    """lines[lo] 为某键所在行，返回其子块范围 (lo+1, end)（end 为首个缩进 ≤ indent 的非空行）。"""
    end = hi
    for j in range(lo + 1, hi):
        line = lines[j]
        if not line.strip():
            continue
        if _indent(line) <= indent:
            end = j
            break
    return lo + 1, end


def append_pos(lines, lo, hi):
    """块内最后一个非空行之后的位置（用于追加，跳过尾部空行）。"""
    j = hi
    while j > lo and not lines[j - 1].strip():
        j -= 1
    return j


def fmt_id(mid):
    """按 YAML 纯标量安全规则决定是否加单引号（与文件原有无引号风格一致）。"""
    if not mid:
        return "''"
    special = '-?:,[]{}#&*!|>\'"%@`'
    need = ((':' in mid) or ('#' in mid) or mid[0] in special
            or mid.strip().lower() in ('true', 'false', 'null', 'yes', 'no', 'on', 'off', '~')
            or mid != mid.strip())
    if need:
        return "'" + mid.replace("'", "''") + "'"
    return mid


def patch_insert(lines, inserts):
    """inserts = [(pos, [文本行])]，按 pos 从大到小插入，避免索引错位。"""
    for pos, new in sorted(inserts, key=lambda x: -x[0]):
        lines[pos:pos] = [l if l.endswith('\n') else l + '\n' for l in new]


# ---------- 主流程 ----------

def main():
    profile, dry = parse_args(sys.argv[1:])
    path = os.path.join(DSH_HOME, 'profiles', profile, 'cordis.patch.yml')
    if not os.path.exists(path):
        raise SystemExit(f'找不到 dsh 配置文件: {path}（可用 --profile 指定，或设 DSH_HOME/DSH_PROFILE）')

    with open(path) as f:
        text = f.read()
    doc = yaml.safe_load(text)
    if not isinstance(doc, list):
        raise SystemExit(f'{path}: 顶层不是 Cordis patch 条目列表')
    entry = next((e for e in doc if isinstance(e, dict) and e.get('id') == LLM_ENTRY_ID), None)
    if entry is None:
        raise SystemExit(f'{path}: 未找到 id: {LLM_ENTRY_ID} 的 patch 条目')
    providers = (entry.get('config') or {}).get('providers') or {}

    pi = pi_cache.load()
    out = []

    # 1) 结构化判断需要哪些变更
    plan = []  # [(dsh 渠道 key, [模型条目 dict], [provider 字段行缩进内容])]
    for pname, pdata in pi['providers'].items():
        if pname in SKIP_CHANNELS:
            out.append(f'跳过 {pname}: 不同步（价格数据不正确）')
            continue
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
        # 模型源：kilo/openrouter 从上游提取免费模型，其他渠道用 pi models
        if pname in UPSTREAM_FREE:
            try:
                items = fetch_free.fetch_free_models(pname)
            except Exception as e:
                items = pdata.get('models', [])
                out.append(f'{pname}: 上游提取失败（{e}），回退 pi models')
        else:
            items, dropped = pi_cache.filter_models(pi, pname, pdata.get('models', []))
            if dropped:
                out.append(f'{pname}: 剔除失效模型 {dropped}（实时 /models 不再存在）')
        existing = {m['id'] for m in (prov.get('models') or []) if isinstance(m, dict)}
        todo = [m for m in items if m.get('id') not in existing]
        # provider 级字段：已有值不更新，仅空值补充
        fills = []
        if not prov.get('baseURL') and pdata.get('baseUrl'):
            fills.append(('baseURL', pdata['baseUrl']))
            out.append(f'{pname}: baseURL 空值补充')
        if not prov.get('api'):
            fills.append(('api', pdata.get('api') or 'openai-completions'))
            out.append(f'{pname}: api 空值补充')
        if todo or fills:
            plan.append((key, todo, fills))
        out.append(f'{pname}: 新增模型 {len(todo)} 个 {[m["id"] for m in todo] if todo else ""}')

    if not plan:
        print('无变更：dsh 已包含 pi 全部模型（未写入文件）')
        print('\n'.join(out))
        return

    # 2) 文本级插入
    lines = text.splitlines(keepends=True)
    bounds = entry_bounds(lines, LLM_ENTRY_ID)
    if bounds is None:
        raise SystemExit(f'{path}: 文本层未定位到 `- id: {LLM_ENTRY_ID}` 条目（格式异常，未写入）')
    start, end = bounds
    e_indent = _indent(lines[start])
    cfg = find_key_line(lines, start + 1, end, e_indent + 2, 'config')
    if cfg is None:
        raise SystemExit(f'{path}: {LLM_ENTRY_ID} 条目缺少 config 段（未写入）')
    clo, chi = block_bounds(lines, cfg, end, e_indent + 2)
    prov = find_key_line(lines, clo, chi, e_indent + 4, 'providers')
    if prov is None:
        raise SystemExit(f'{path}: {LLM_ENTRY_ID}.config 缺少 providers 段（未写入）')
    plo, phi = block_bounds(lines, prov, chi, e_indent + 4)

    inserts = []
    for key, todo, fills in plan:
        ch = find_key_line(lines, plo, phi, e_indent + 6, key)
        if ch is None:
            out.append(f'跳过 {key}: 文本层未定位（格式异常）')
            continue
        chlo, chhi = block_bounds(lines, ch, phi, e_indent + 6)
        m_indent, item_indent = e_indent + 8, e_indent + 10
        model_lines = []
        for m in todo:
            mid = m['id']
            model_lines.append(' ' * item_indent + '- id: ' + fmt_id(mid))
            # 视觉模型显式声明模态（dsh 手动录入模型默认纯文本）
            if 'image' in (m.get('input') or []):
                model_lines.append(' ' * (item_indent + 2) + 'input: [text, image]')
        field_lines = [' ' * m_indent + f'{k}: {v}' for k, v in fills]
        ml = find_key_line(lines, chlo, chhi, m_indent, 'models')
        if ml is None:  # 渠道无 models 段：字段行 + models 头 + 模型行，一起追加到渠道段末尾
            seg = field_lines + [' ' * m_indent + 'models:'] + model_lines
            if seg:
                inserts.append((append_pos(lines, chlo, chhi), seg))
            continue
        mlo, mhi = block_bounds(lines, ml, chhi, m_indent)
        if model_lines:
            inserts.append((append_pos(lines, mlo, mhi), model_lines))
        if field_lines:  # 插在 models 段之前，避免被当成 models 列表内容
            inserts.append((ml, field_lines))
    patch_insert(lines, inserts)

    if dry:
        print(f'[dry-run] 将写入 {path}：{len(inserts)} 处插入')
        print('\n'.join(out))
        return

    stamp = datetime.date.today().strftime('%Y%m%d')
    shutil.copy(path, path + '.bak-' + stamp)
    with open(path, 'w') as f:  # 覆盖写，保留原文件权限（0600）
        f.write(''.join(lines))

    # 3) 断言校验：只允许 models 新增 + provider 空值字段补充
    bak = yaml.safe_load(open(path + '.bak-' + stamp))
    new = yaml.safe_load(open(path))
    assert [e.get('id') for e in bak] == [e.get('id') for e in new], 'patch 条目 id 或顺序被改动'
    for b, n in zip(bak, new):
        if b.get('id') != LLM_ENTRY_ID:
            assert b == n, f"条目 {b.get('id')} 被改动"
    bcfg = (next(e for e in bak if e.get('id') == LLM_ENTRY_ID).get('config') or {})
    ncfg = (next(e for e in new if e.get('id') == LLM_ENTRY_ID).get('config') or {})
    assert [k for k in bcfg if k != 'providers'] == [k for k in ncfg if k != 'providers'], 'config 键序被改动'
    for k in bcfg:
        if k != 'providers':
            assert bcfg[k] == ncfg.get(k), f'config.{k} 被改动'
    bprov, nprov = bcfg.get('providers') or {}, ncfg.get('providers') or {}
    assert list(bprov.keys()) == list(nprov.keys()), 'provider 键序被改动'
    for k in nprov:
        bm = [m for m in (bprov[k].get('models') or []) if isinstance(m, dict)]
        nm = [m for m in (nprov[k].get('models') or []) if isinstance(m, dict)]
        assert [m['id'] for m in bm] == [m['id'] for m in nm[:len(bm)]], f'{k}: 现有模型条目被改动/删除'
        for kk, vv in bprov[k].items():
            if kk == 'models':
                continue
            if kk in ('baseURL', 'api'):
                assert nprov[k].get(kk) == vv or (not vv and nprov[k].get(kk)), f'{k}: {kk} 被改动（已有值）'
            else:
                assert nprov[k].get(kk) == vv, f'{k}: 字段 {kk} 被改动'
    print(f'校验通过：仅 models 新增（写入 {path}）')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
