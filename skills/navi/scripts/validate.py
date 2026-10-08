#!/usr/bin/env python3
"""校验 navi cheatsheet 语法。

用法:
  python3 validate.py path/to/foo.cheat [--strict] [--fix]
  python3 validate.py path/to/dir  # 批量校验目录下所有 .cheat/.cheat.md

检查项:
  - tags / 描述 / 命令完整性
  - <var> 与 $ var: 的一致性（含 @ 依赖继承）
  - --- 选项合法性（shellwords 解析、数值、必填值）
  - 续行闭合、Markdown 块闭合
  - 重复 cheat（fnv 去重）提示
"""

import argparse
import re
import shlex
import sys
from pathlib import Path

VAR_LINE_RE = re.compile(r"^\$\s*([^:]+):(.*)")
VAR_USE_RE = re.compile(r"<([A-Za-z0-9_]+)>")
KNOWN_FLAGS_WITH_VALUE = {
    "--column", "--map", "--delimiter", "--query", "--filter",
    "--preview", "--preview-window", "--header", "--fzf-overrides",
    "--headers", "--header-lines",
}
KNOWN_FLAGS_NO_VALUE = {"--multi", "--prevent-extra", "--expand"}
KNOWN_FLAGS = KNOWN_FLAGS_WITH_VALUE | KNOWN_FLAGS_NO_VALUE


def fnv(s: str) -> int:
    h = 2166136261
    for b in s.encode():
        h = (h * 16777619) & 0xFFFFFFFF
        h ^= b
    return h


def parse_args():
    p = argparse.ArgumentParser(description="校验 navi cheatsheet")
    p.add_argument("path", help=".cheat 文件或目录")
    p.add_argument("--strict", action="store_true", help="将 warning 视为 error")
    p.add_argument("--fix", action="store_true", help="原地修复：去尾空格、补末尾换行")
    return p.parse_args()


def validate_file(path: Path, fix: bool = False):
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if fix:
        fixed = [l.rstrip() for l in lines]
        new_text = "\n".join(fixed) + "\n"
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            lines = new_text.splitlines()

    errors: list[str] = []
    warnings: list[str] = []

    inside = False
    snippet_start = -1
    for i, line in enumerate(lines, 1):
        if line.startswith("```"):
            if not inside:
                inside = True
                snippet_start = i
            else:
                inside = False
    if inside:
        errors.append(f"line {snippet_start}: Markdown 代码块未闭合（缺 ```）")

    cont = False
    cont_start = -1
    for i, line in enumerate(lines, 1):
        if cont:
            if not line.endswith("\\"):
                cont = False
        elif line.startswith("$") and line.endswith("\\"):
            cont = True
            cont_start = i
    if cont:
        warnings.append(f"line {cont_start}: 变量定义续行未闭合（末行以 \\ 结尾）")

    seen_hashes: dict[int, str] = {}
    declared_global: dict[str, set[str]] = {}
    dependencies: dict[str, list[str]] = {}  # tags -> [dep_tags]

    cur_tags = ""
    cur_comment = ""
    cur_snippet_lines: list[str] = []
    cur_used: set[str] = set()
    cur_declared: set[str] = set()
    cur_flush_line = 1
    inside_snippet = False
    cont_buf = ""

    def flush(line_no: int, is_final: bool = False):
        nonlocal cur_tags, cur_comment, cur_snippet_lines, cur_used, cur_declared
        snippet = "\n".join(cur_snippet_lines).strip()
        tags = cur_tags.strip()
        comment = cur_comment.strip()
        if not tags and not comment and not snippet:
            return
        if not comment or not snippet:
            if is_final and tags:
                if not comment:
                    warnings.append(f"line {line_no}: tags '{tags}' 缺少 # 描述")
                if not snippet:
                    warnings.append(f"line {line_no}: tags '{tags}' 缺少命令")
            else:
                return
            if not comment or not snippet:
                return

        h = fnv(f"{tags}{comment}{snippet}")
        if h in seen_hashes:
            warnings.append(f"line {line_no}: 重复 cheat（与 {seen_hashes[h]} 重复，已去重）")
        else:
            seen_hashes[h] = f"line {line_no}"

        # 合并依赖声明
        tags_declared = set(declared_global.get(tags, set())) | cur_declared
        for dep in dependencies.get(tags, []):
            tags_declared |= declared_global.get(dep, set())
        undefined = cur_used - tags_declared
        for v in sorted(undefined):
            warnings.append(f"line {line_no}: 变量 <{v}> 在命令中使用但未定义 $ {v}:（将提示手输）")
        unused = cur_declared - cur_used
        for v in sorted(unused):
            warnings.append(f"line {line_no}: 变量 ${v} 已定义但未在命令中使用")

    for idx, raw in enumerate(lines):
        line_no = idx + 1
        line = raw

        if not line.strip() and not inside_snippet and not cont_buf:
            if cur_snippet_lines:
                cur_snippet_lines.append("")
            continue

        if line.startswith("```"):
            inside_snippet = not inside_snippet
            continue

        if inside_snippet:
            cur_snippet_lines.append(line)
            for v in VAR_USE_RE.findall(line):
                cur_used.add(v)
            continue

        if cont_buf or (line.startswith("$") and ":" in line and line.endswith("\\")):
            if not cont_buf:
                cont_buf = line.rstrip("\\")
                if line.endswith("\\"):
                    continue
            else:
                cont_buf += line.rstrip("\\")
                if line.endswith("\\"):
                    continue
                line = cont_buf
                cont_buf = ""
        if cont_buf:
            cont_buf += line.rstrip("\\")
            if line.endswith("\\"):
                continue
            line = cont_buf
            cont_buf = ""

        if line.startswith("%"):
            flush(cur_flush_line, is_final=False)
            if cur_tags.strip():
                declared_global.setdefault(cur_tags.strip(), set()).update(cur_declared)
            cur_tags = line[1:].strip()
            cur_flush_line = line_no
            if not cur_tags:
                errors.append(f"line {line_no}: % 行缺少 tags")
            cur_comment = ""
            cur_snippet_lines = []
            cur_used = set()
            cur_declared = set()
        elif line.startswith("@"):
            val = line[1:].strip()
            if not val:
                warnings.append(f"line {line_no}: @ 行缺少依赖 tags")
            else:
                key = cur_tags.strip()
                if key:
                    dependencies.setdefault(key, []).append(val)
        elif line.startswith(";"):
            continue
        elif line.startswith("#"):
            flush(cur_flush_line, is_final=False)
            if cur_tags.strip():
                declared_global.setdefault(cur_tags.strip(), set()).update(cur_declared)
            cur_comment = line[1:].strip()
            cur_flush_line = line_no
            cur_snippet_lines = []
            cur_used = set()
            cur_declared = set()
        elif line.startswith("$"):
            m = VAR_LINE_RE.match(line)
            if not m:
                errors.append(f"line {line_no}: 变量行格式错误，应为 $ var: command（缺冒号）: {line[:80]}")
                continue
            var_name = m.group(1).strip()
            rest = m.group(2)
            if not var_name:
                errors.append(f"line {line_no}: 变量名为空")
                continue
            if not re.match(r"^[A-Za-z0-9_]+$", var_name):
                errors.append(f"line {line_no}: 变量名 '{var_name}' 非法，仅允许 [A-Za-z0-9_]")
                continue
            cur_declared.add(var_name)
            if "---" in rest:
                _, opts_str = rest.split("---", 1)
                opts_str = opts_str.strip()
                if not opts_str:
                    warnings.append(f"line {line_no}: --- 后无选项")
                else:
                    try:
                        parts = shlex.split(opts_str)
                    except ValueError as e:
                        errors.append(f"line {line_no}: 选项引号未闭合: {e}")
                        continue
                    i = 0
                    while i < len(parts):
                        flag = parts[i]
                        if flag in KNOWN_FLAGS_NO_VALUE:
                            i += 1
                        elif flag in KNOWN_FLAGS_WITH_VALUE:
                            if i + 1 >= len(parts):
                                errors.append(f"line {line_no}: 选项 {flag} 缺少值")
                                break
                            val2 = parts[i + 1]
                            if flag in ("--column", "--header-lines", "--headers"):
                                try:
                                    n = int(val2)
                                    if not (0 <= n <= 255):
                                        errors.append(f"line {line_no}: {flag} 值 {val2} 超出 u8 范围")
                                except ValueError:
                                    errors.append(f"line {line_no}: {flag} 值 '{val2}' 非整数")
                            i += 2
                        elif flag.startswith("--"):
                            warnings.append(f"line {line_no}: 未知选项 {flag}")
                            i += 1
                            if i < len(parts) and not parts[i].startswith("--"):
                                i += 1
                        else:
                            warnings.append(f"line {line_no}: 选项解析异常，意外 token '{flag}'")
                            i += 1
        else:
            cur_snippet_lines.append(line)
            for v in VAR_USE_RE.findall(line):
                cur_used.add(v)

    flush(cur_flush_line, is_final=True)

    level = "error" if errors else ("warning" if warnings else "ok")
    return errors, warnings, level


def main():
    args = parse_args()
    p = Path(args.path)
    targets: list[Path] = []
    if p.is_dir():
        targets = sorted(p.rglob("*.cheat")) + sorted(p.rglob("*.cheat.md"))
        if not targets:
            print(f"目录 {p} 下未找到 .cheat/.cheat.md 文件")
            sys.exit(1)
    elif p.is_file():
        targets = [p]
    else:
        print(f"路径不存在: {p}", file=sys.stderr)
        sys.exit(2)

    total_errors = 0
    total_warnings = 0
    for t in targets:
        errs, warns, level = validate_file(t, fix=args.fix)
        prefix = f"{t}:"
        if level == "ok":
            print(f"{prefix} OK")
        for e in errs:
            print(f"{prefix} ERROR: {e}", file=sys.stderr)
        for w in warns:
            out = sys.stderr if args.strict else sys.stdout
            tag = "ERROR" if args.strict else "WARN"
            print(f"{prefix} {tag}: {w}", file=out)
        total_errors += len(errs)
        if args.strict:
            total_errors += len(warns)
        else:
            total_warnings += len(warns)

    if total_errors:
        print(f"\n校验失败: {total_errors} error(s), {total_warnings} warning(s)", file=sys.stderr)
        sys.exit(1)
    if total_warnings:
        print(f"\n校验通过（有警告）: {total_warnings} warning(s)")
        sys.exit(0)
    print("\n校验通过")
    sys.exit(0)


if __name__ == "__main__":
    main()
