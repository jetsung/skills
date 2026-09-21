# 图片压缩与转存（>1MB 场景）

当候选图片 >1MB 时，不直接转存，而是先用本地压缩工具尝试压到 <1MB，再转存到论坛图床；若两工具都压不下来（压缩失败或压缩后仍 ≥1MB），则回退到原图 URL（**不加代理前缀**）。

## 压缩工具简介

可用工具（安装脚本均托管于 `fx4.cn`）：

- **oxipng** — 用 Rust 编写的多线程 PNG 无损压缩优化工具（[oxipng/oxipng](https://github.com/oxipng/oxipng)）。仅支持 PNG，实测 1.32 MB PNG 可压到 812 KB，**PNG 首选**。
- **rimage** — 用 Rust 编写的批量图片压缩/格式转换工具，支持 PNG/JPEG/WebP/AVIF（[vlad-salone/rimage](https://github.com/vlad-salone/rimage)）。通用作 oxipng 的兜底（对 PNG 反而可能变大）。
- **resvg** — 高性能 SVG 渲染器，可将 SVG 转换为 PNG 等位图（[linebender/resvg](https://github.com/linebender/resvg)）。用于把 SVG 先渲染成 PNG，再交给 oxipng / rimage 压缩。

## 工具安装（未安装时自动安装）

运行前检查 `oxipng`、`rimage`（如涉及 SVG 再检查 `resvg`）是否已安装，缺失则用下列命令安装（安装脚本由用户托管于 `fx4.cn`）：

```bash
which oxipng >/dev/null 2>&1 || curl -L fx4.cn/oxipng | bash
which rimage >/dev/null 2>&1 || curl -L fx4.cn/rimage | bash
which resvg  >/dev/null 2>&1 || curl -L fx4.cn/resvg | bash
```

安装后验证：`oxipng --version`、`rimage --version`、`resvg --version` 应能正常执行。

**沙箱 / 受限环境下的两个坑（实测）**：

1. **PATH 里可能没有 `/usr/local/bin`**，导致 `which oxipng` 误判为未安装——工具其实早就装好了。检测时按绝对路径兜底：
   ```bash
   for t in oxipng rimage resvg; do
     p=$(command -v $t || echo "/usr/local/bin/$t")
     [ -x "$p" ] && echo "$t -> $p"
   done
   ```
   命中绝对路径后直接用绝对路径调用（`/usr/local/bin/oxipng ...`），别再跑安装脚本。
2. **`fx4.cn` 安装脚本在本机必失败**：它解压到 `/tmp`，而 `/tmp` 只有 10 MB 的 tmpfs，还会因 `Cannot change ownership to uid 1001` 报错退出。不要反复重试安装脚本；改为手动装（解压加 `--no-same-owner`，装到 PATH 内可写目录如 `~/.local/bin`）：
   ```bash
   tar --no-same-owner -xzf <包>.tar.gz -C <工作区目录>
   install -m 755 <包>/oxipng ~/.local/bin/oxipng
   ```
   （`/usr/bin`、`/usr/local/bin` 在沙箱里可能是只读的，写入前先 `touch` 测一下。）

## 压缩算法（两工具互相兜底）

对单个 >1MB 图片，按以下流程处理（两个工具互为兜底：一个不行就换另一个，不重复尝试已失败的工具）：

1. 下载原图到本地临时文件（受 SKILL.md「网络规则（中国网络代理）」约束）。
2. 依次尝试 `oxipng` 与 `rimage`（顺序不限），**任一工具满足「压缩成功 且 结果 <1MB」即采用该产物并停止尝试**：
   - `oxipng -o max --strip safe --out <out.png> <in.png>`（仅处理 PNG；非 PNG 直接判定该工具不可用，换下一个）。注意 oxipng 10.x 的 `-o` 是优化级别、输出文件必须用 `--out`，写成 `... <in> -o <out>` 会报 usage 错误。实测：1.32 MB 的 PNG 用这条命令可压到 812 KB。
   - `rimage png --directory <输出目录> --suffix _min <in.png>`（通用格式，需带子命令如 `png`/`webp`/`mozjpeg`；输出到 `--directory` 并加 `--suffix`，不支持「输入+输出」两个位置参数写法）。**实测它对 PNG 反而会变大**（1.35 MB → 8 MB），所以 PNG 优先用 oxipng，rimage 只作兜底。
   - GIF / 动图两个工具都处理不了（oxipng 只吃 PNG，rimage 无 gif 子命令），会走到「两工具都失败」分支，直接引用原图 URL。
3. **命中（某工具成功且 <1MB）**：将该产物转存到论坛图床（如 `flarum-images.w.idev.top`），正文使用协议相对地址 `//host/path`。
4. **两工具都失败 / 结果仍 ≥1MB**：放弃压缩，直接引用原图 URL，**不加代理前缀**（即 `https://raw.githubusercontent.com/...` 原样，不套 `filetas.asfd.cn`）。

> 兜底判定：「压缩不了」= 命令报错、不支持该格式、或进程非零退出；「压缩后还是大于 1M」= 压缩成功但字节数 ≥1048576。任一情形都立即切换到另一个工具；两个都不行才回退原图 URL。
