#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_tags.py — 获取 Flarum 标签列表并缓存到 ~/.cache/flarum_idev_tags
（Python 版，等价于上游 fetch_tags.sh）

用法:
    fetch_tags.py [--force]

环境变量: FLARUM_URL (必填), FLARUM_TOKEN (必填), FLARUM_USER_ID (可选)。
"""
import json
import os
import sys

import requests

TAGS_CACHE = os.path.expanduser("~/.cache/flarum_idev_tags")
ENV_KEYS = ("FLARUM_URL", "FLARUM_TOKEN", "FLARUM_USER_ID")


def load_env():
    env = {k: os.environ.get(k, "") for k in ENV_KEYS}
    missing = [k for k in ("FLARUM_URL", "FLARUM_TOKEN") if not env[k]]
    if missing:
        sys.stderr.write(
            "错误: 环境变量缺少 %s。请向用户索取论坛地址与 API 密钥后以环境变量传入。\n"
            % "、".join(missing)
        )
        sys.exit(1)
    return env


def main():
    force = "--force" in sys.argv[1:]

    if not force and os.path.isfile(TAGS_CACHE):
        sys.stderr.write("标签缓存已存在: %s（使用 --force 刷新）\n" % TAGS_CACHE)
        return

    env = load_env()
    auth = "Token %s" % env["FLARUM_TOKEN"]
    if env["FLARUM_USER_ID"]:
        auth += "; userId=%s" % env["FLARUM_USER_ID"]

    os.makedirs(os.path.dirname(TAGS_CACHE), exist_ok=True)

    try:
        r = requests.get(
            "%s/api/tags?include=parent" % env["FLARUM_URL"],
            headers={"Authorization": auth},
            timeout=60,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        sys.stderr.write("获取标签列表失败: %s\n" % e)
        sys.exit(1)

    with open(TAGS_CACHE, "w", encoding="utf-8") as f:
        f.write(r.text)

    doc = r.json()
    tags = [t for t in doc.get("data", []) + doc.get("included", []) if t.get("type") == "tags"]
    sys.stderr.write("标签缓存已保存: %s\n" % TAGS_CACHE)
    for t in tags:
        a = t.get("attributes", {})
        print("%4s  %-25s %s" % (t["id"], a.get("slug", ""), a.get("name", "")))


if __name__ == "__main__":
    main()
