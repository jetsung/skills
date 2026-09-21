#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reply.py — 在已有讨论下回帖（POST /api/posts）

用法:
    reply.py <discussion_id> <正文文件|->

示例:
    reply.py 1234 /tmp/tutorial.md
    cat /tmp/tutorial.md | reply.py 1234 -

特点:
    - 直接用 requests 调 POST /api/posts，避免 bash 转义问题（与 publish.py 一致）。
    - 环境变量 FLARUM_URL / FLARUM_TOKEN / FLARUM_USER_ID 优先取自身环境；
      缺失时回退读取 ~/.workbuddy/settings.json。
"""
import json
import os
import sys

import requests

SETTINGS_PATH = os.path.expanduser("~/.workbuddy/settings.json")


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


def usage():
    return """用法: reply.py <discussion_id> <正文文件|->

在已有讨论下回帖（POST /api/posts）。

参数:
  discussion_id  讨论的数字 ID（从讨论链接 $FLARUM_URL/d/<id> 中取得）
  正文文件|-     Markdown 文件路径；`-` 表示从 stdin 读入

选项:
  -h, --help    显示本帮助并退出

输出: 成功时向 stdout 打印「回帖成功: <论坛地址>/d/<id>[/<楼层号>]」；错误打到 stderr。
退出码: 0 成功；1 失败（参数无效 / 环境变量缺失 / HTTP 4xx/5xx，stderr 附响应详情）。

示例:
  reply.py 1234 /tmp/tutorial.md
  cat /tmp/tutorial.md | reply.py 1234 -

依赖: python3 + requests；环境变量 FLARUM_URL / FLARUM_TOKEN（必填）、
      FLARUM_USER_ID（可选）。缺失时自动回退读取 ~/.workbuddy/settings.json。
"""


def main():
    args = sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print(usage())
        sys.exit(0)
    if len(args) < 2:
        sys.stderr.write(
            "错误: 参数不足，需要 <discussion_id> 和 <正文文件|->。\n"
            "用法: %s <discussion_id> <正文文件|->\n" % sys.argv[0]
        )
        sys.exit(1)
    discussion_id, content_file = args[0], args[1]

    if not discussion_id.isdigit():
        sys.stderr.write(
            '错误: discussion_id 必须是数字 ID，收到 "%s"。\n'
            "讨论 ID 从讨论链接 $FLARUM_URL/d/<id> 中取得。\n" % discussion_id
        )
        sys.exit(1)

    env = load_env()

    if content_file == "-":
        content = sys.stdin.read()
    else:
        with open(content_file, encoding="utf-8") as f:
            content = f.read()

    payload = {
        "data": {
            "type": "posts",
            "attributes": {"content": content},
            "relationships": {
                "discussion": {"data": {"type": "discussions", "id": discussion_id}}
            },
        }
    }

    auth = "Token %s" % env["FLARUM_TOKEN"]
    if env["FLARUM_USER_ID"]:
        auth += "; userId=%s" % env["FLARUM_USER_ID"]

    try:
        resp = requests.post(
            "%s/api/posts" % env["FLARUM_URL"],
            headers={"Authorization": auth, "Content-Type": "application/json"},
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=60,
        )
    except requests.RequestException as e:
        sys.stderr.write("回帖请求失败: %s\n" % e)
        sys.exit(1)

    if resp.status_code >= 400:
        sys.stderr.write("回帖失败 (HTTP %d):\n%s\n" % (resp.status_code, resp.text[:800]))
        sys.exit(1)

    post = resp.json()["data"]
    number = post.get("attributes", {}).get("number", "")
    print("回帖成功: %s/d/%s%s" % (
        env["FLARUM_URL"], discussion_id, ("/%s" % number) if number else ""
    ))


if __name__ == "__main__":
    main()
