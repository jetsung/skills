#!/usr/bin/env python3
"""opencode → mimocode 同步（覆盖式：provider 整块替换；密钥写明文实值）。

用法:
    python3 scripts/sync-opencode-to-mimocode.py
    python3 scripts/sync-opencode-to-mimocode.py --dry-run   # 只打印计划不写文件

流程约定（与 sync-pi-to-mimocode.py 配套）:
    1. 先 `sync-pi-to-opencode.py` 把 pi 基准合并进 opencode（占位符风格）
    2. 再跑本脚本：从 opencode 提取 provider，**清空并整块覆盖** mimocode 的 provider

行为:
- 源: ~/.config/opencode/opencode.json 的 `provider` 对象
- 目标: ~/.config/mimocode/mimocode.jsonc（或 mimocode.json），仅替换 `provider` 键
- **密钥解析为明文**：mimocode 不认 opencode 的 `{env:VAR}` 占位符，写入前把
  `options.apiKey` / `options.baseURL` / `headers.*` 中的占位符解析为环境变量实值
  （支持 `{env:VAR}`、`!echo -n "$VAR"`、`"$VAR"`、`${VAR}`）；优先级：env 实值 >
  目标已有明文 > 空。运行前需在已注入密钥环境变量的 shell 中执行。
- 非 provider 顶层字段（mcp/agent/skills 等）原样保留；`$schema` 规范为 mimocode 地址
- provider 缺失 `npm` 时兜底补 `@ai-sdk/openai-compatible`（源已补全则原样带入），已有值不动
- 自动备份（.bak-YYYYMMDD-HHMMSS）；写后断言仅密钥字段被解析、结构与源一致
- 密钥不回显，只报告 provider/模型计数与已解析的 env 名
"""
import argparse
import copy
import datetime
import json
import os
import re
import shutil
import sys

sys.dont_write_bytecode = True

OC_PATH = os.path.expanduser('~/.config/opencode/opencode.json')
MIMO_CANDIDATES = (
    os.path.expanduser('~/.config/mimocode/mimocode.jsonc'),
    os.path.expanduser('~/.config/mimocode/mimocode.json'),
    os.path.expanduser('~/.config/mimocode/config.json'),
)
MIMO_SCHEMA = 'https://mimo.xiaomi.com/mimocode/config.json'
NPM_DEFAULT = '@ai-sdk/openai-compatible'

# 占位符 → 环境变量名
_ENV_BRACE = re.compile(r'^\{env:([A-Z0-9_]+)\}$')
_ENV_ECHO_RE = re.compile(r'^!echo -n "\$([A-Z0-9_]+)"$')
_ENV_DOLLAR = re.compile(r'^\$\{?([A-Z0-9_]+)\}$')


def strip_jsonc(text):
    """去掉 // 与 /* */ 注释和尾逗号，返回可 json.loads 的文本。字符串字面量内的内容不动。"""
    out = []
    i, n = 0, len(text)
    in_str = esc = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '/':
            while i < n and text[i] != '\n':
                i += 1
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '*':
            i += 2
            while i + 1 < n and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return json.loads(re.sub(r',(\s*[}\]])', r'\1', ''.join(out)))


def load_json(path):
    text = open(path, encoding='utf-8').read()
    if path.endswith('.jsonc') or text.lstrip().startswith('//') or '/*' in text[:200]:
        try:
            return strip_jsonc(text)
        except json.JSONDecodeError:
            pass
    return json.loads(text)


def resolve_mimo_path():
    existing = [p for p in MIMO_CANDIDATES if os.path.isfile(p)]
    if existing:
        for p in reversed(MIMO_CANDIDATES):
            if p in existing:
                return p
    return MIMO_CANDIDATES[0]


def count_models(provider):
    return sum(len((cfg or {}).get('models') or {}) for cfg in provider.values())


def ensure_npm(provider):
    """缺失/为空的 provider 补默认适配器 npm（插在 options 之前），返回补全的渠道名列表。"""
    fixed = []
    for pid, cfg in provider.items():
        if not isinstance(cfg, dict) or cfg.get('npm'):
            continue
        items = list(cfg.items())
        cfg.clear()
        inserted = False
        for k, v in items:
            if k == 'options' and not inserted:
                cfg['npm'] = NPM_DEFAULT
                inserted = True
            cfg[k] = v
        if not inserted:
            cfg['npm'] = NPM_DEFAULT
        fixed.append(pid)
    return fixed


def env_name_of(value):
    """识别占位符，返回环境变量名；非占位符返回 None。"""
    if not isinstance(value, str) or not value:
        return None
    for pat in (_ENV_BRACE, _ENV_ECHO_RE, _ENV_DOLLAR):
        m = pat.match(value)
        if m:
            return m.group(1)
    return None


def resolve_secret(value, notes, where, keep=None):
    """占位符 → 环境变量明文实值；明文原样返回。
    env 未设置时：keep 有明文则保留 keep（目标已有值），否则写空。notes 只记 env 名与状态。"""
    name = env_name_of(value)
    if name is None:
        return value
    real = os.environ.get(name, '')
    if real:
        notes.append(f'{where}:{name}→实值')
        return real
    if keep:
        notes.append(f'{where}:{name}→保留目标已有明文(env未设置)')
        return keep
    notes.append(f'{where}:{name}→空(env未设置)')
    return ''


def resolve_provider_secrets(provider, previous=None):
    """深拷贝 provider 并把 options/headers 中的密钥占位符解析为明文。
    previous 为覆盖前的 mimocode provider（用于 env 未设置时保留已有明文）。
    返回 (resolved_provider, notes)。"""
    resolved = copy.deepcopy(provider)
    previous = previous or {}
    notes = []

    def keep_of(pid, *path):
        cur = previous.get(pid)
        for p in path:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(p)
        return cur if isinstance(cur, str) and cur and not env_name_of(cur) else None

    for pid, cfg in resolved.items():
        opts = cfg.get('options') or {}
        for field in ('apiKey', 'baseURL', 'enterpriseUrl'):
            if field in opts:
                opts[field] = resolve_secret(
                    opts[field], notes, f'{pid}.options.{field}',
                    keep=keep_of(pid, 'options', field))
        for hk, hv in list((opts.get('headers') or {}).items()):
            opts['headers'][hk] = resolve_secret(hv, notes, f'{pid}.options.headers.{hk}')
        for mid, mcfg in (cfg.get('models') or {}).items():
            mopts = (mcfg or {}).get('options') or {}
            for field in ('apiKey', 'baseURL'):
                if field in mopts:
                    mopts[field] = resolve_secret(mopts[field], notes, f'{pid}.models.{mid}.options.{field}')
            for hk, hv in list((mopts.get('headers') or {}).items()):
                mopts['headers'][hk] = resolve_secret(hv, notes, f'{pid}.models.{mid}.headers.{hk}')
            for hk, hv in list(((mcfg or {}).get('headers') or {}).items()):
                mcfg['headers'][hk] = resolve_secret(hv, notes, f'{pid}.models.{mid}.headers.{hk}')
    return resolved, notes


def strip_secret_fields(provider):
    """去掉密钥相关字段，用于结构对比（解析前后应完全一致）。"""
    out = copy.deepcopy(provider)
    for cfg in out.values():
        opts = cfg.get('options') or {}
        for field in ('apiKey', 'baseURL', 'enterpriseUrl'):
            opts.pop(field, None)
        opts.pop('headers', None)
        for mcfg in (cfg.get('models') or {}).values():
            mcfg = mcfg or {}
            mopts = mcfg.get('options') or {}
            mopts.pop('apiKey', None)
            mopts.pop('baseURL', None)
            mopts.pop('headers', None)
            mcfg.pop('headers', None)
    return out


def main():
    ap = argparse.ArgumentParser(description='opencode provider → mimocode 整块覆盖（密钥明文）')
    ap.add_argument('--dry-run', action='store_true', help='只打印计划，不写文件')
    args = ap.parse_args()

    if not os.path.isfile(OC_PATH):
        sys.exit(f'源不存在: {OC_PATH}')

    dst = resolve_mimo_path()
    oc = load_json(OC_PATH)
    src_provider = oc.get('provider')
    if not isinstance(src_provider, dict) or not src_provider:
        sys.exit('opencode 配置无 provider 段或为空，拒绝覆盖')
    npm_fixed = ensure_npm(src_provider)

    if os.path.isfile(dst):
        mimo = load_json(dst)
    else:
        mimo = {}
    if not isinstance(mimo, dict):
        sys.exit(f'目标配置不是对象: {dst}')

    # 占位符 → 明文（mimocode 不认 {env:XXX}）；env 未设置时保留 mimocode 已有明文
    prev_provider = mimo.get('provider')
    if not isinstance(prev_provider, dict):
        prev_provider = {}
    resolved_provider, notes = resolve_provider_secrets(src_provider, prev_provider)

    old_ids = sorted(prev_provider.keys())
    new_ids = sorted(resolved_provider.keys())
    old_n = count_models(prev_provider)
    new_n = count_models(resolved_provider)
    removed = sorted(set(old_ids) - set(new_ids))
    added = sorted(set(new_ids) - set(old_ids))

    print(f'源:   {OC_PATH}')
    print(f'目标: {dst}')
    print(f'provider: {len(old_ids)} → {len(new_ids)}  (新增 {added or "无"} / 移除 {removed or "无"})')
    print(f'模型条目: {old_n} → {new_n}')
    print('策略: provider 整块覆盖（非合并）；密钥占位符解析为明文；其余顶层字段保留')
    if npm_fixed:
        print(f'npm 兜底补全: {len(npm_fixed)} 个 provider {npm_fixed}（{NPM_DEFAULT}）')
    print(f'密钥解析: {len(notes)} 处')
    for n in notes:
        print(f'  {n}')

    if args.dry_run:
        print('[dry-run] 未写入')
        return

    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bak_mimo = {}
    if os.path.isfile(dst):
        bak = f'{dst}.bak-{stamp}'
        shutil.copy2(dst, bak)
        bak_mimo = load_json(bak)
        print(f'备份: {bak}')

    mimo['provider'] = resolved_provider
    mimo['$schema'] = MIMO_SCHEMA

    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(mimo, f, ensure_ascii=False, indent=2)
        f.write('\n')

    # 断言：写后等于「解析后的源」；结构（去掉密钥字段）与源一致；非 provider 字段不动
    written = load_json(dst)
    assert written.get('provider') == resolved_provider, 'provider 写后与解析结果不一致'
    assert strip_secret_fields(written['provider']) == strip_secret_fields(src_provider), \
        '除密钥字段外，provider 结构与 opencode 源不一致'
    for k, v in bak_mimo.items():
        if k in ('provider', '$schema'):
            continue
        assert written.get(k) == v, f'非 provider 字段被改动: {k}'
    assert written.get('$schema') == MIMO_SCHEMA
    # 残留占位符检查：明文写入后不应再有 {env: / !echo
    leftover = []
    for pid, cfg in written['provider'].items():
        for field in ('apiKey', 'baseURL'):
            val = (cfg.get('options') or {}).get(field)
            if env_name_of(val):
                leftover.append(f'{pid}.options.{field}')
    assert not leftover, f'仍残留密钥占位符: {leftover}'

    print('校验通过：密钥已明文化，结构与源一致，其余字段保留')
    print(f'完成：{dst} 已覆盖为 {len(new_ids)} 个 provider / {new_n} 个模型条目')


if __name__ == '__main__':
    main()
