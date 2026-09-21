#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upload_image.py — 转存图片到论坛图床（Flarum fof/upload 插件）
（Python 版，等价于上游 upload_image.sh）

用法:
    upload_image.py <图片URL|本地文件> [更多...]

示例:
    upload_image.py https://raw.githubusercontent.com/owner/repo/main/assets/a.png
    upload_image.py ./local.png https://example.com/b.jpg

输出: 每个输入一行「<来源>\\t<论坛图床URL>」，图床地址为协议相对形式（//host/path）
依赖: python3 + requests；环境变量 FLARUM_URL / FLARUM_TOKEN（必填）、
      FLARUM_USER_ID（可选）、IS_CHINA（可选，=1 时启用代理前缀降级）。
      缺失时自动回退读取 ~/.workbuddy/settings.json。
"""
import json
import mimetypes
import os
import re
import sys
import tempfile

import requests

SETTINGS_PATH = os.path.expanduser("~/.workbuddy/settings.json")
PROXY = "https://filetas.asfd.cn"
MAX_BYTES = 4194304  # 论坛限制 4096 kb，留一点余量

# mimetypes 默认不认 webp/avif，显式补一张表
EXTRA_MIME = {
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
}


def load_env():
    env = {
        "FLARUM_URL": os.environ.get("FLARUM_URL", ""),
        "FLARUM_TOKEN": os.environ.get("FLARUM_TOKEN", ""),
        "FLARUM_USER_ID": os.environ.get("FLARUM_USER_ID", ""),
        "IS_CHINA": os.environ.get("IS_CHINA", ""),
    }
    if not env["FLARUM_URL"] or not env["FLARUM_TOKEN"]:
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                s = json.load(f)
            for k in ("FLARUM_URL", "FLARUM_TOKEN", "FLARUM_USER_ID", "IS_CHINA"):
                env[k] = env[k] or s.get(k, "")
        except FileNotFoundError:
            pass
    return env


def raw_to_api(url):
    """GitHub raw 地址 -> api.github.com 等价地址（raw 被墙/被代理阻断时的兜底）。"""
    m = re.match(r"https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)$", url)
    if not m:
        return None
    owner, repo, ref, path = m.groups()
    return "https://api.github.com/repos/%s/%s/contents/%s?ref=%s" % (owner, repo, path, ref)


def fetch_image(url, out):
    """下载图片到本地；三重降级：直连 -> api.github.com -> 代理前缀。成功返回 True。"""
    env = load_env()
    # 1) 直连
    try:
        r = requests.get(url, timeout=60)
        if r.status_code == 200 and r.content:
            with open(out, "wb") as f:
                f.write(r.content)
            return True
    except requests.RequestException:
        pass
    # 2) GitHub raw -> api.github.com
    api = raw_to_api(url)
    if api:
        try:
            r = requests.get(api, headers={"Accept": "application/vnd.github.raw"}, timeout=60)
            if r.status_code == 200 and r.content:
                with open(out, "wb") as f:
                    f.write(r.content)
                return True
        except requests.RequestException:
            pass
    # 3) 中国网络环境走代理前缀
    if env.get("IS_CHINA") == "1":
        try:
            r = requests.get("%s/%s" % (PROXY, url), timeout=60)
            if r.status_code == 200 and r.content:
                with open(out, "wb") as f:
                    f.write(r.content)
                return True
        except requests.RequestException:
            pass
    return False


def to_protocol_relative(u):
    """统一成协议相对形式：//host/path（正文里不需要 http:/https: 前缀）。"""
    u = re.sub(r"^https?:", "", u)
    return u if u.startswith("//") else "//" + u.lstrip("/")


def upload_one(src, env, tmp_root):
    if os.path.isfile(src):
        file = src
    else:
        name = os.path.basename(src.split("?")[0]) or "image"
        file = os.path.join(tmp_root, name)
        if not fetch_image(src, file):
            sys.stderr.write("下载失败: %s\n" % src)
            return None

    size = os.path.getsize(file)
    if size > MAX_BYTES:
        sys.stderr.write("文件过大（%d 字节，上限 %d）: %s\n" % (size, MAX_BYTES, src))
        return None

    ext = os.path.splitext(file)[1].lower()
    mime = EXTRA_MIME.get(ext) or mimetypes.guess_type(file)[0] or "application/octet-stream"

    auth = "Token %s" % env["FLARUM_TOKEN"]
    if env["FLARUM_USER_ID"]:
        auth += "; userId=%s" % env["FLARUM_USER_ID"]

    try:
        with open(file, "rb") as fh:
            r = requests.post(
                "%s/api/fof/upload" % env["FLARUM_URL"],
                headers={"Authorization": auth},
                files={"files[]": (os.path.basename(file), fh, mime)},
                timeout=60,
            )
        r.raise_for_status()
        doc = r.json()
    except (requests.RequestException, ValueError) as e:
        sys.stderr.write("上传失败: %s (%s)\n" % (src, e))
        return None

    files = doc.get("data") or []
    if not files:
        sys.stderr.write("响应解析失败（无 data）: %s\n" % src)
        return None
    url = to_protocol_relative(files[0]["attributes"]["url"])
    return url


def usage():
    return """用法: upload_image.py [选项] <图片URL|本地文件> [更多...]

把图片（本地文件或远程 URL）转存到论坛图床（fof/upload），输出图床地址。

选项:
  -h, --help    显示本帮助并退出

输出: 每个输入一行「<来源>\\t<图床URL>」（数据走 stdout，错误走 stderr）；
      图床地址为协议相对形式（//host/path），可直接写进正文。
退出码: 0 全部成功；1 部分或全部失败（失败原因逐行打到 stderr）。

示例:
  upload_image.py https://raw.githubusercontent.com/owner/repo/main/assets/a.png
  upload_image.py ./local.png https://example.com/b.jpg

依赖: python3 + requests；环境变量 FLARUM_URL / FLARUM_TOKEN（必填）、
      FLARUM_USER_ID（可选）、IS_CHINA（可选，=1 时启用代理前缀降级）。
      缺失时自动回退读取 ~/.workbuddy/settings.json。
"""


def main():
    args = sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print(usage())
        sys.exit(0)
    if not args:
        sys.stderr.write("错误: 缺少图片参数（图片 URL 或本地文件路径）。\n")
        sys.stderr.write("用法: %s <图片URL|本地文件> [更多...]\n" % sys.argv[0])
        sys.exit(1)
    env = load_env()
    if not env["FLARUM_URL"] or not env["FLARUM_TOKEN"]:
        sys.stderr.write("错误: 未设置 FLARUM_URL / FLARUM_TOKEN（环境变量或 %s 中均缺失）\n" % SETTINGS_PATH)
        sys.exit(1)

    tmp_root = tempfile.mkdtemp(prefix="flarum_up_")
    status = 0
    try:
        for src in sys.argv[1:]:
            url = upload_one(src, env, tmp_root)
            if url is None:
                status = 1
            else:
                print("%s\t%s" % (src, url))
    finally:
        import shutil
        shutil.rmtree(tmp_root, ignore_errors=True)
    sys.exit(status)


if __name__ == "__main__":
    main()
