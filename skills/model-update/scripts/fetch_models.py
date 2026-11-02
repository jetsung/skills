#!/usr/bin/env python3
"""抓取上游渠道的模型列表并缓存为 JSONC。

用法：
    PYTHONDONTWRITEBYTECODE=1 python3 scripts/fetch_models.py <channel>

渠道标识推导环境变量前缀：转大写、非字母数字替换为下划线，
例如 sense-ai -> SENSE_AI_BASE_URL / SENSE_AI_API_KEY。

成功时把 /models 原始响应原子写入 ~/.cache/models/<channel 小写>.jsonc，
保留上游全部字段；任何失败都不覆盖已有缓存，且不输出密钥。

请求 /models 优先用 curl（部分服务器如 apihub.agnes-ai.com 对 Python urllib 的
TLS 握手稳定挂起，OpenSSL 3.5.9 与服务器不兼容），curl 失败/不可用时回退 urllib。
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
import subprocess
import urllib.request

CACHE_DIR = os.path.join("~", ".cache", "models")
TIMEOUT = 30


def env_prefix(channel: str) -> str:
    prefix = re.sub(r"[^0-9A-Za-z]+", "_", channel.strip()).strip("_").upper()
    if not prefix:
        raise ValueError(f"无法从渠道标识推导环境变量名: {channel!r}")
    return prefix


def cache_path(channel: str) -> str:
    return os.path.join(os.path.expanduser(CACHE_DIR), f"{channel.strip().lower()}.jsonc")


def _curl_get(url: str, api_key: str, timeout: int = TIMEOUT) -> tuple[int, str] | None:
    """curl 主请求（GET）。部分服务器（如 apihub.agnes-ai.com）对 Python urllib 的
    TLS 握手稳定挂起（OpenSSL 3.5.9 与服务器不兼容），故优先 curl。
    返回 (HTTP 码, 响应文本)；curl 不可用或异常返回 None（由调用方回退 urllib）。"""
    try:
        out = subprocess.run(
            ["curl", "-s", "-m", str(timeout), "-w", "\n%{http_code}",
             "-H", f"Authorization: Bearer {api_key}",
             "-H", "Accept: application/json", url],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        text = out.stdout
        if "\n" not in text:
            return None
        body, code_str = text.rsplit("\n", 1)
        return int(code_str), body
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def _request_models(base_url: str, api_key: str) -> object:
    """抓取 /models。优先 curl（TLS 栈更通用，部分服务器对 urllib 握手挂起）；
    curl 失败/不可用时回退 urllib。"""
    url = base_url.rstrip("/") + "/models"
    curl_res = _curl_get(url, api_key)
    if curl_res is not None:
        code, body = curl_res
        if code == 200 and body.strip():
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                pass  # curl 响应非 JSON，回退 urllib
    # urllib 兜底（curl 不可用、异常或响应非 JSON）
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_models(payload: object) -> list[dict]:
    models = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(models, list) or not models:
        raise ValueError("响应中没有非空模型数组")
    if not all(isinstance(m, dict) for m in models):
        raise ValueError("模型数组包含非对象元素")
    return models


def _write_jsonc(path: str, payload: dict, source_url: str) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    header = f"// source: {source_url}\n// fetched_at: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n"
    text = header + json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".jsonc")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def fetch(channel: str) -> tuple[str, int]:
    prefix = env_prefix(channel)
    base_url = os.environ.get(f"{prefix}_BASE_URL", "").strip()
    api_key = os.environ.get(f"{prefix}_API_KEY", "").strip()

    missing = []
    if not base_url:
        missing.append(f"{prefix}_BASE_URL")
    if not api_key:
        missing.append(f"{prefix}_API_KEY")
    if missing:
        raise RuntimeError("缺少必要环境变量: " + ", ".join(missing))

    payload = _request_models(base_url, api_key)
    models = _extract_models(payload)
    normalized = payload if isinstance(payload, dict) else {"data": payload}

    path = cache_path(channel)
    _write_jsonc(path, normalized, base_url)
    return path, len(models)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("用法: fetch_models.py <channel>", file=sys.stderr)
        return 2

    try:
        path, count = fetch(argv[1])
    except Exception as exc:  # 错误信息不含密钥
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    print(f"已缓存 {count} 个模型 -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
