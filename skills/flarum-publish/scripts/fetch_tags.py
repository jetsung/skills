#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_tags.py — 获取 Flarum 标签列表并缓存到 ~/.cache/flarum_idev_tags
（Python 版，等价于上游 fetch_tags.sh）

用法:
    fetch_tags.py [--force]

环境变量: FLARUM_URL (必填), FLARUM_TOKEN (必填), FLARUM_USER_ID (可选);
          缺失时自动回退读取 ~/.workbuddy/settings.json。
"""
import json
import os
import sys

import requests

SETTINGS_PATH = os.path.expanduser("~/.workbuddy/settings.json")
TAGS_CACHE = os.path.expanduser("~/.cache/flarum_idev_tags")


def load_env():
    env = {
        "FLARUM_URL": os.environ.get("FLARUM_URL", ""),
        "FLARUM_TOKEN": os.environ.get("FLARUM_TOKEN", ""),
        "FLARUM_USER_ID": os.environ.get("FLARUM_USER_ID", ""),
    }
    if not env["FLARUM_URL"] or not env["FLARUM_TOKEN"]:
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                s = json.load(f)
            env["FLARUM_URL"] = env["FLARUM_URL"] or s.get("FLARUM_URL", "")
            env["FLARUM_TOKEN"] = env["FLARUM_TOKEN"] or s.get("FLARUM_TOKEN", "")
            env["FLARUM_USER_ID"] = env["FLARUM_USER_ID"] or s.get("FLARUM_USER_ID", "")
        except FileNotFoundError:
            pass
    if not env["FLARUM_URL"]:
        sys.stderr.write("错误: 未设置 FLARUM_URL（环境变量或 %s 中均缺失）\n" % SETTINGS_PATH)
        sys.exit(1)
    if not env["FLARUM_TOKEN"]:
        sys.stderr.write("错误: 未设置 FLARUM_TOKEN（环境变量或 %s 中均缺失）\n" % SETTINGS_PATH)
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
