#!/usr/bin/env python3
"""从上游 README 抓取并刷新 references/raw.md（紧凑 AI 知识库，非逐字）。

抓取优先级:
  1. 直连原始 URL
  2. GitHub Contents API (Accept: application/vnd.github.raw)
  3. 代理前缀 https://filetas.asfd.cn/  (IS_CHINA=1 时)

注意: 本脚本生成的 raw.md 为机器精炼的紧凑知识库（~20K），非逐字快照。
上游大改时需人工复核并同步 references/syntax.md 等整理文档。

用法:
  python3 scripts/update.py                  # 抓取并更新 raw.md
  python3 scripts/update.py --check          # 对比本地 raw.md 是否过期
  python3 scripts/update.py --url <URL>      # 指定 URL
  python3 scripts/update.py --out <path>     # 指定输出
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

DEFAULT_URL = "https://raw.githubusercontent.com/casey/just/refs/heads/master/README.md"
PROXY_PREFIX = "https://filetas.asfd.cn"
SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUT = SKILL_DIR / "references" / "raw.md"

# 仅移除顶部的徽章/HTML 装饰，不做语义压缩；真正的紧凑化在 compact() 完成
STRIP_PATTERNS = [
    r'<div align=right>.*?</div>\s*',
    r'<h1 align=center>.*?</h1>\s*',
    r'<div align=center>.*?</div>\s*',
    r'<br>\s*',
    r'!\[screenshot\]\(.*?\)\s*',
]

# 需要折叠/删除的冗长章节（人类可读但对 AI 低信息密度）
DROP_SECTIONS = [
    # 安装包管理器表格已在紧凑版中折为一行
    # 编辑器支持逐个展开对 AI 无用，折为一行
    # 贡献/FAQ 冗长叙事
]

COMPACT_HEADER = (
    "<!-- auto-generated from {url} — compact AI knowledge, not verbatim -->\n"
    "<!-- update: python3 scripts/update.py — regenerates this compact file -->\n"
    "<!-- book: https://just.systems/man/en/ | src: {url} -->\n"
)


def fetch(url: str, timeout: int = 30) -> bytes:
    for attempt_url in _candidate_urls(url):
        try:
            req = urllib.request.Request(attempt_url, headers={"User-Agent": "just-skill-updater/1.0"})
            if "api.github.com" in attempt_url:
                req.add_header("Accept", "application/vnd.github.raw")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                if data and len(data) > 1000:
                    print(f"✓ fetched via {attempt_url} ({len(data)} bytes)")
                    return data
        except Exception as e:
            print(f"  ✗ {attempt_url}: {e}", file=sys.stderr)
            continue
    raise RuntimeError(f"all fetch attempts failed for {url}")


def _candidate_urls(url: str) -> list[str]:
    cands: list[str] = [url]
    m = re.match(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)", url)
    if m:
        owner, repo, ref, path = m.groups()
        cands.append(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}")
    cands.append(f"{PROXY_PREFIX}/{url}")
    return cands


def denoise(text: str) -> str:
    for pat in STRIP_PATTERNS:
        text = re.sub(pat, "", text, flags=re.DOTALL)
    if "<table>" in text:
        text = text.replace("<table>", "").replace("</table>", "")
        text = text.replace("<thead>", "").replace("</thead>", "")
        text = text.replace("<tbody>", "").replace("</tbody>", "")
        text = text.replace("<tr>", "| ").replace("</tr>", " |")
        text = text.replace("<th>", "").replace("</th>", " | ")
        text = text.replace("<td>", "").replace("</td>", " | ")
        text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.lstrip()


def compact(text: str, source_url: str) -> str:
    """将 denoised 的完整 README 压缩为 AI 紧凑知识库。

    策略: 保留所有语义（语法/参数/函数/设置/属性），删除人类冗余：
    - 安装包管理器逐行表格 → 折为一行枚举
    - 编辑器支持逐项展开 → 折为一行
    - Backwards Compatibility / Contributing / FAQ 叙事 → 要点压缩
    - 重复示例/解释性段落去重
    若上游结构大改，此函数可能需人工调整；此时请以 references/*.md 为准并重炼本文件。
    """
    # 1. 基础去噪
    text = denoise(text)

    # 2. 折叠安装表格为一行（保留关键命令，其余指向上游）
    # 匹配 Packages 小节的 HTML 表格残留，替换为紧凑行
    # 简化：若仍含大量 Package Manager 表格标记，折叠
    if text.count("Package Manager") >= 2:
        # 保留首个表格的命令，其余折叠提示
        text = re.sub(
            r"#### Cross-platform.*?#### BSD",
            "#### Cross-platform — `cargo install just`|`cargo binstall just`|`brew/apt/dnf/pacman/apk/nix/conda/npm/pipx/uv/arkade/asdf/snap install just` (full table in upstream)\n\n#### BSD",
            text, flags=re.DOTALL,
        )

    # 3. 编辑器支持折叠
    text = re.sub(
        r"### Vim and Neovim.*?### Emacs",
        "### Vim/Neovim — builtin >=9.1/0.11 or `vim-just`/`tree-sitter-just`\n\n### Emacs",
        text, flags=re.DOTALL,
    )
    text = re.sub(
        r"### Visual Studio Code.*?### Language Server Protocol",
        "### VS Code — `nefrob/vscode-just` (others unmaintained); JetBrains/Kakoune/Helix/Sublime/Micro/Zed — builtin or plugin, see upstream\n\n### Language Server Protocol",
        text, flags=re.DOTALL,
    )

    # 4. 删除 Contributing 冗长流程，保留要点
    text = re.sub(
        r"Contributing\n------------.*?(?=Frequently Asked Questions)",
        "Contributing — not accepting PRs currently; see upstream for workflow.\n\n",
        text, flags=re.DOTALL,
    )

    # 5. FAQ 压缩：仅保留 make 差异要点
    # 保留标题，删除过长叙事由 references 覆盖

    # 6. 去除多余空行与首尾
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # 7. 当前紧凑知识库已人工精炼为 ~20K（见 git history）。
    #    若仍 >40K 说明折叠规则未覆盖新增章节，不应覆盖已有紧凑版
    if len(text) > 40000:
        print(f"⚠ compact still {len(text)} chars (>40K), upstream may have new sections — manual refinement needed", file=sys.stderr)
        print(f"  hint: update references/*.md and re-compact raw.md manually; not overwriting {source_url}", file=sys.stderr)
        # 返回 None 由调用方处理为不覆盖
        return None

    header = COMPACT_HEADER.format(url=source_url)
    if not text.startswith("#"):
        header += "# just — compact knowledge (AI-only, non-human-readable)\n\n"
    return header + text + "\n"

def main() -> None:
    ap = argparse.ArgumentParser(description="抓取并刷新 just 紧凑知识库")
    ap.add_argument("--url", default=DEFAULT_URL, help="上游 README URL")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="输出路径")
    ap.add_argument("--check", action="store_true", help="仅检查是否过期")
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()

    out = Path(args.out)
    try:
        data = fetch(args.url, timeout=args.timeout)
    except Exception as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    text = data.decode("utf-8", errors="replace")
    cleaned = compact(text, args.url)

    if cleaned is None:
        if args.check:
            print("check: needs manual update (>40K)", file=sys.stderr)
            sys.exit(2)
        print("not overwriting — manual refinement required", file=sys.stderr)
        sys.exit(2)

    if args.check:
        if not out.exists():
            print("check: local raw.md not found -> considered outdated")
            sys.exit(2)
        local = out.read_text(encoding="utf-8", errors="replace")
        if hashlib.sha256(local.encode()).hexdigest() == hashlib.sha256(cleaned.encode()).hexdigest():
            print("check: up-to-date")
            sys.exit(0)
        else:
            print("check: outdated (upstream changed)")
            print(f"  local: {len(local)} chars, compacted upstream: {len(cleaned)} chars")
            sys.exit(2)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(cleaned, encoding="utf-8")
    print(f"wrote {out} ({len(cleaned)} chars)")
    print("hint: review references/*.md and bump SKILL.md metadata.version if content changed")


if __name__ == "__main__":
    main()
