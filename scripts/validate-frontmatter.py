#!/usr/bin/env python3
"""校验 skills/ 下所有 SKILL.md 的 YAML frontmatter。

用法：
    uv run --with pyyaml python scripts/validate-frontmatter.py [skills/]

校验项（依据 Agent Skills 规范 https://agentskills.io/）：
- frontmatter 存在且为合法 YAML 映射
- name：必填，1-64 字符，仅小写字母/数字/连字符，不以连字符开头结尾、无连续连字符，且与父目录名一致
- description：必填，1-1024 字符
- license / compatibility：可选字符串
- metadata：可选，键值均为字符串
- allowed-tools：可选字符串
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
STRING_FIELDS = ("license", "compatibility", "allowed-tools")


def check_skill(skill_dir: Path) -> list[str]:
    """校验单个 skill 目录，返回错误列表（空列表即通过）。"""
    errors: list[str] = []
    path = skill_dir / "SKILL.md"
    if not path.exists():
        return [f"{skill_dir}: 缺少 SKILL.md"]

    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return [f"{path}: 缺少 YAML frontmatter"]

    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        return [f"{path}: frontmatter 不是合法 YAML：{e}"]
    if not isinstance(fm, dict):
        return [f"{path}: frontmatter 必须是键值映射"]

    # name
    name = fm.get("name")
    if name is None:
        errors.append("缺少必填字段 name")
    elif not isinstance(name, str):
        errors.append(f"name 必须是字符串，实际为 {type(name).__name__}")
    else:
        if not (1 <= len(name) <= 64):
            errors.append(f"name 长度须为 1-64，实际 {len(name)}")
        if not NAME_RE.match(name):
            errors.append(f"name 仅允许小写字母/数字/连字符且不以连字符开头结尾：{name!r}")
        if name != skill_dir.name:
            errors.append(f"name {name!r} 与目录名 {skill_dir.name!r} 不一致")

    # description
    desc = fm.get("description")
    if desc is None:
        errors.append("缺少必填字段 description")
    elif not isinstance(desc, str):
        errors.append(f"description 必须是字符串，实际为 {type(desc).__name__}")
    elif not (1 <= len(desc) <= 1024):
        errors.append(f"description 长度须为 1-1024，实际 {len(desc)}")

    # 可选字符串字段
    for key in STRING_FIELDS:
        if key in fm and not isinstance(fm[key], str):
            errors.append(f"{key} 必须是字符串")

    # metadata：字符串 -> 字符串映射
    if "metadata" in fm:
        meta = fm["metadata"]
        if not isinstance(meta, dict):
            errors.append("metadata 必须是映射")
        else:
            for k, v in meta.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    errors.append(f"metadata.{k} 的键值必须均为字符串")

    # 未知字段提示
    known = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    unknown = set(fm) - known
    if unknown:
        errors.append(f"存在规范外字段：{', '.join(sorted(unknown))}")

    return [f"{path}: {e}" for e in errors]


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "skills")
    if not root.is_dir():
        print(f"错误：目录不存在 {root}", file=sys.stderr)
        return 2

    skill_dirs = sorted(p for p in root.iterdir() if p.is_dir())
    if not skill_dirs:
        print(f"错误：{root} 下没有 skill 目录", file=sys.stderr)
        return 2

    all_errors: list[str] = []
    for d in skill_dirs:
        errs = check_skill(d)
        mark = "OK " if not errs else "FAIL"
        print(f"[{mark}] {d}")
        all_errors.extend(errs)

    if all_errors:
        print(f"\n{len(all_errors)} 个错误：")
        for e in all_errors:
            print(f"  - {e}")
        return 1
    print(f"\n全部 {len(skill_dirs)} 个 skill 的 frontmatter 校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
