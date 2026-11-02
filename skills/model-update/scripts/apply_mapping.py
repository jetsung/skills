#!/usr/bin/env python3
"""按 `目标字段=源字段` 映射把源缓存中的每个模型转换为目标平台条目。

用法：
    PYTHONDONTWRITEBYTECODE=1 python3 scripts/apply_mapping.py \
        --source ~/.cache/models/sense.jsonc \
        --mapping ~/.cache/models/pi_from_sense.env \
        [--output /tmp/models.json]

脚本只做机械字段复制：不含任何渠道或平台的内置映射，也不做单位换算。
模型 id 原样保留；源模型缺少某个映射字段时省略该目标字段。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile


def _strip_jsonc(text: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue

        if ch == "/" and i + 1 < len(text) and text[i + 1] == "*":
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue

        out.append(ch)
        i += 1
    return "".join(out)


def load_jsonc(path: str) -> object:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    cleaned = _strip_jsonc(text)
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
    return json.loads(cleaned)


def load_models(path: str) -> list[dict]:
    payload = load_jsonc(path)
    models = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(models, list) or not models:
        raise ValueError(f"{path}: 没有非空模型数组")
    if not all(isinstance(m, dict) for m in models):
        raise ValueError(f"{path}: 模型数组包含非对象元素")
    return models


def load_mapping(path: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise ValueError(f"{path}:{lineno}: 缺少 '='")
            target, source = (part.strip() for part in line.split("=", 1))
            if not target or not source:
                raise ValueError(f"{path}:{lineno}: 目标字段或源字段为空")
            mapping[target] = source
    if not mapping:
        raise ValueError(f"{path}: 映射为空")
    return mapping


def convert(models: list[dict], mapping: dict[str, str]) -> list[dict]:
    converted = []
    for index, model in enumerate(models):
        model_id = model.get("id")
        if not isinstance(model_id, str) or not model_id:
            raise ValueError(f"第 {index + 1} 个源模型缺少有效 id")

        item = {"id": model_id}
        for target, source in mapping.items():
            if target == "id" or target in item or source not in model:
                continue
            item[target] = model[source]
        converted.append(item)
    return converted


def _write_output(path: str, items: list[dict]) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按字段映射转换模型条目")
    parser.add_argument("--source", required=True, help="源缓存 JSONC 路径")
    parser.add_argument("--mapping", required=True, help="映射 env 文件路径")
    parser.add_argument("--output", help="输出 JSON 路径；省略时写到 stdout")
    args = parser.parse_args(argv)

    try:
        models = load_models(args.source)
        mapping = load_mapping(args.mapping)
        converted = convert(models, mapping)
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    if args.output:
        _write_output(args.output, converted)
        print(f"已转换 {len(converted)} 个模型 -> {args.output}")
    else:
        json.dump(converted, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
