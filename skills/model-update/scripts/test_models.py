#!/usr/bin/env python3
"""实测渠道模型可用性（chat/completions 最小请求），并标注生图/多模态输出模型。

用法：
    PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_models.py <channel> [模型id ...]

渠道标识推导环境变量前缀与 fetch_models.py 一致：sense-ai -> SENSE_AI_BASE_URL / SENSE_AI_API_KEY。
待测模型：显式给出 id 则只测这些；否则读源缓存 ~/.cache/models/<channel>.jsonc 的全部模型
（缓存缺失时先运行 fetch_models.py）。

判定规则（与 model-channel-sync 一致）：
- HTTP 200 且 choices 的 content/reasoning 有值 → 可用
- HTTP 429（rate limit / inference exceeds tpm/rpm limit）→ 可用（临时限流，模型存在，不得剔除）
- HTTP 404 model is not found 且模型在 /models 缓存列表中 → 生图模型（只走 /images/generations，
  404 即判定信号，无需二次探测；不得写入 pi/omp 配置）
- HTTP 403 含 region / not available in the current token plan → 不可用（地区/套餐限制）
- 其余（401 鉴权、404 且列表无此模型、5xx、连接失败）→ 不可用

多模态预筛：缓存条目 output_modalities/output 不含 text（图/视频/音频输出）或 id 含 ocr 的
模型不发起 chat 实测，直接标注剔除。

退出码：0 至少一个可用；1 全部不可用；2 凭据/缓存缺失。不输出密钥。
"""

from __future__ import annotations

import json
import os
import re
import sys
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


def load_cache_models(channel: str) -> list[dict]:
    """读取源缓存（jsonc：跳过 // 注释行）。"""
    path = cache_path(channel)
    if not os.path.exists(path):
        raise FileNotFoundError(f"源缓存不存在: {path}（先运行 fetch_models.py）")
    raw = "".join(line for line in open(path, encoding="utf-8")
                  if not line.lstrip().startswith("//"))
    data = json.loads(raw)
    models = data.get("data") if isinstance(data, dict) else data
    if not isinstance(models, list):
        raise ValueError("源缓存中没有模型数组")
    return [m for m in models if isinstance(m, dict) and m.get("id")]


def _curl_post(url: str, api_key: str, body: str, timeout: int = TIMEOUT):
    """curl 主请求（POST），返回 (HTTP 码, 响应文本)；curl 不可用/异常返回 None。"""
    try:
        out = subprocess.run(
            ["curl", "-s", "-m", str(timeout), "-w", "\n%{http_code}",
             "-X", "POST",
             "-H", f"Authorization: Bearer {api_key}",
             "-H", "Content-Type: application/json",
             "-d", body, url],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        text = out.stdout
        if "\n" not in text:
            return None
        resp, code_str = text.rsplit("\n", 1)
        return int(code_str), resp
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def probe_chat(base_url: str, api_key: str, mid: str) -> tuple[str, str]:
    """单模型 chat 实测。返回 (状态, 说明)；状态 ∈ 可用/生图模型/不可用（生图在主流程按列表判定）。"""
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps({"model": mid,
                       "messages": [{"role": "user", "content": "ping"}],
                       "max_tokens": 8, "stream": False})
    res = _curl_post(url, api_key, body)
    if res is None:  # urllib 兜底
        try:
            req = urllib.request.Request(url, data=body.encode(), headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return judge(r.status, r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            return judge(e.code, detail)
        except Exception as e:
            return "不可用", f"连接失败: {e}"
    return judge(*res)


def judge(code: int, resp: str) -> tuple[str, str]:
    err_msg = ""
    if code != 429:
        try:
            d = json.loads(resp)
        except json.JSONDecodeError:
            d = None
        if code == 200:
            if not isinstance(d, dict) or not d.get("choices"):
                return "不可用", f"HTTP 200 但响应无 choices: {resp[:120]}"
            msg = (d["choices"][0] or {}).get("message") or {}
            if msg.get("content") or msg.get("reasoning"):
                return "可用", "HTTP 200（content/reasoning 有值）"
            return "可用", "HTTP 200（有 choices）"
        if isinstance(d, dict) and d.get("error"):
            e = d["error"]
            err_msg = (e.get("message", "") if isinstance(e, dict) else str(e)) or resp[:120]
        else:
            err_msg = resp[:120]
    if code == 429:
        return "可用", "HTTP 429 限流（临时限额，模型存在）"
    if code == 404 and re.search(r"not[_ ]?found", err_msg, re.I):
        return "生图模型?", f"HTTP 404: {err_msg[:150]}"  # 主流程按是否在 /models 列表最终定性
    if re.search(r"region", err_msg, re.I):
        return "不可用", f"地区限制 — HTTP {code}: {err_msg[:150]}"
    if re.search(r"token plan|403", err_msg, re.I) or code == 403:
        return "不可用", f"套餐不提供该模型 — HTTP {code}: {err_msg[:150]}"
    return "不可用", f"HTTP {code}: {err_msg[:150]}"


def is_non_text_output(m: dict) -> bool:
    out = m.get("output_modalities") or m.get("output") or []
    return bool(out) and "text" not in [str(x).lower() for x in out]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("用法: test_models.py <channel> [模型id ...]", file=sys.stderr)
        return 2
    channel = argv[1]
    prefix = env_prefix(channel)
    base_url = os.environ.get(f"{prefix}_BASE_URL", "").strip()
    api_key = os.environ.get(f"{prefix}_API_KEY", "").strip()
    if not base_url or not api_key:
        missing = [f"{prefix}_{n}" for n, v in (("BASE_URL", base_url), ("API_KEY", api_key)) if not v]
        print(f"错误: 缺少必要环境变量: {', '.join(missing)}", file=sys.stderr)
        return 2

    try:
        cached = load_cache_models(channel)
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    api_ids = {m["id"] for m in cached}

    targets = argv[2:] or [m["id"] for m in cached]
    results: dict[str, tuple[str, str]] = {}
    skipped: list[str] = []
    by_id = {m["id"]: m for m in cached}
    for mid in targets:
        m = by_id.get(mid, {})
        if is_non_text_output(m) or "ocr" in mid.lower():
            skipped.append(mid)
            results[mid] = ("剔除", "多模态输出/OCR，不发起 chat 实测，不入同步")
            continue
        status, note = probe_chat(base_url, api_key, mid)
        if status == "生图模型?":
            if mid in api_ids:
                status, note = "生图模型", f"HTTP 404 但 /models 列表存在 → 走生图接口，不入 pi/omp（{note}）"
            else:
                status, note = "不可用", f"HTTP 404 且 /models 无此模型，判定失效 — {note}"
        results[mid] = (status, note)
        print(f"  {mid}: {status} — {note}")

    ok = [m for m, (s, _) in results.items() if s == "可用"]
    img = [m for m, (s, _) in results.items() if s == "生图模型"]
    bad = [m for m, (s, _) in results.items() if s == "不可用"]
    print(f"\n小结: 可用 {len(ok)} | 生图模型 {len(img)}（不入 pi/omp）| 不可用 {len(bad)}"
          f" | 预筛剔除 {len(skipped)}")
    if ok:
        print("  可写入: " + ", ".join(ok))
    if img:
        print("  生图（不写入，如需使用走 /images/generations）: " + ", ".join(img))
    if bad:
        print("  不可用（不写入）: " + ", ".join(bad))
    if skipped:
        print("  预筛剔除: " + ", ".join(skipped))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
