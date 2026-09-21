#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish.py — 发布文章到 Flarum 论坛（Python 版，等价于上游 publish.sh）

用法:
    publish.py <标题> <正文文件|-> [标签1,标签2]

示例:
    publish.py "ZeroClaw：自托管的 Rust AI 智能体运行时" /tmp/article.md "63,86,20"
    cat /tmp/article.md | publish.py "标题" -

特点:
    - 直接用 requests 调 POST /api/discussions，避免 bash 历史扩展（标题/URL 中 `!` 被改坏）这类转义问题。
    - 环境变量 FLARUM_URL / FLARUM_TOKEN / FLARUM_USER_ID 从进程环境读取，
      不依赖任何 agent 私有配置文件；缺失时脚本报错退出，由 agent 向用户索取。
    - 标签解析与上游一致：逗号分隔的 ID / 名称 / slug 均可，纯数字视为 ID；
      标签缓存 ~/.cache/flarum_idev_tags 不存在时自动调用 fetch_tags.py 获取。
"""
import json
import os
import sys

import requests

TAGS_CACHE = os.path.expanduser("~/.cache/flarum_idev_tags")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
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


def parse_tags(tag_input):
    """逗号分隔的 ID / 名称 / slug -> [{'type':'tags','id':...}]。无输入返回 None。"""
    if not tag_input:
        return None
    if not os.path.isfile(TAGS_CACHE):
        fetch = os.path.join(SCRIPT_DIR, "fetch_tags.py")
        if os.path.isfile(fetch):
            try:
                import subprocess
                subprocess.run([sys.executable, fetch], check=True)
            except subprocess.CalledProcessError:
                sys.stderr.write("无法获取标签列表，请先运行 scripts/fetch_tags.py\n")
                sys.exit(1)
    with open(TAGS_CACHE, encoding="utf-8") as f:
        doc = json.load(f)

    tags = []
    for raw in tag_input.split(","):
        name = raw.strip()
        if not name:
            continue
        if name.isdigit():
            tags.append({"type": "tags", "id": name})
            continue
        low = name.lower()
        found = None
        for t in doc.get("data", []) + doc.get("included", []):
            if t.get("type") != "tags":
                continue
            a = t.get("attributes", {})
            if low in (a.get("name", "").lower(), a.get("slug", "").lower(), t.get("id", "")):
                found = t["id"]
                break
        if found is None:
            avail = ", ".join(
                t["attributes"]["name"] for t in doc.get("data", []) if t.get("type") == "tags"
            )
            sys.stderr.write("错误: 未找到标签「%s」\n可用标签: %s\n" % (name, avail))
            sys.exit(1)
        tags.append({"type": "tags", "id": found})
    return tags or None


def usage():
    return """用法: publish.py <标题> <正文文件|-> [标签1,标签2]

把一篇文章发布为论坛讨论（POST /api/discussions）。

参数:
  标题          讨论标题（应与正文第一行 `# <标题>` 一致，不含 `# ` 前缀）
  正文文件|-    Markdown 文件路径；`-` 表示从 stdin 读入
  标签          可选，逗号分隔的标签 ID / 名称 / slug（如 "55,57,21"）

选项:
  -h, --help    显示本帮助并退出

输出: 成功时向 stdout 打印「发布成功: <论坛地址>/d/<id>」；错误打到 stderr。
退出码: 0 成功；1 失败（环境变量缺失 / 参数无效 / HTTP 4xx/5xx，stderr 附响应详情）。

示例:
  publish.py "ZeroClaw：自托管的 Rust AI 智能体运行时" /tmp/article.md "63,86,20"
  cat /tmp/article.md | publish.py "标题" -

依赖: python3 + requests；环境变量 FLARUM_URL / FLARUM_TOKEN（必填）、
      FLARUM_USER_ID（可选）从进程环境读取，无配置文件回退。
"""


def main():
    args = sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print(usage())
        sys.exit(0)
    if len(args) < 2:
        sys.stderr.write(
            "错误: 参数不足，需要 <标题> 和 <正文文件|->（标签可选）。\n"
            "用法: %s <标题> <正文文件|-> [标签1,标签2]\n" % sys.argv[0]
        )
        sys.exit(1)
    title, content_file = args[0], args[1]
    tag_input = args[2] if len(args) > 2 else ""

    env = load_env()

    if content_file == "-":
        content = sys.stdin.read()
    else:
        with open(content_file, encoding="utf-8") as f:
            content = f.read()

    data = {
        "type": "discussions",
        "attributes": {"title": title, "content": content},
    }
    tags = parse_tags(tag_input)
    if tags:
        data["relationships"] = {"tags": {"data": tags}}

    auth = "Token %s" % env["FLARUM_TOKEN"]
    if env["FLARUM_USER_ID"]:
        auth += "; userId=%s" % env["FLARUM_USER_ID"]

    try:
        resp = requests.post(
            "%s/api/discussions" % env["FLARUM_URL"],
            headers={"Authorization": auth, "Content-Type": "application/json"},
            data=json.dumps({"data": data}, ensure_ascii=False).encode("utf-8"),
            timeout=60,
        )
    except requests.RequestException as e:
        sys.stderr.write("发布请求失败: %s\n" % e)
        sys.exit(1)

    if resp.status_code >= 400:
        sys.stderr.write("发布失败 (HTTP %d):\n%s\n" % (resp.status_code, resp.text[:800]))
        sys.exit(1)

    did = resp.json()["data"]["id"]
    print("发布成功: %s/d/%s" % (env["FLARUM_URL"], did))


if __name__ == "__main__":
    main()
