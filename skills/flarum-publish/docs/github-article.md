# 从 GitHub 项目生成文章（整理为论坛格式）

用户提供一个 GitHub 项目链接（如 `https://github.com/<owner>/<repo>`）时，先按 [examples/demo.md](../examples/demo.md) 模板整理成中文文章，再走 SKILL.md 的「发布流程」发布。

## 文章模板（examples/demo.md）

```markdown
# <项目名称>：<项目的简单描述总结>

<项目名称> 是一款<项目描述>。

## 主要功能

- <项目的主要功能与用途>

![项目截图](<图片URL>)

---

<项目开源地址 URL>
<项目官网地址 URL>
```

注意：`# 标题` 一级标题**既是讨论标题，也是文章正文的首行**——发布时它单独作为标题传给 `publish.sh`，同时必须保留在正文第一行（不要删掉）；即正文以 `# <项目名称>：<项目的简单描述总结>` 开头，其后才是简介段。模板末尾的开源地址/官网地址为裸 URL 各占一行，不加列表符号。

## 信息采集

1. **仓库元数据**：`GET https://api.github.com/repos/<owner>/<repo>`（可设 `GITHUB_TOKEN` 避免限流），提取 `description`、`language`、`license`、`homepage`、`topics` 等。
2. **README**：优先 `https://raw.githubusercontent.com/<owner>/<repo>/<默认分支>/README.md`（默认分支取 API 返回的 `default_branch`，可能是 `main` 或 `master`）。中国网络环境（`IS_CHINA=1`）下 raw 域名需加代理前缀 `https://filetas.asfd.cn/`。
   - 若 README 含多语言切换链接（如 openaitx），直接取简体中文版本链接里的原文，或自行翻译英文正文。
   - HTML 片段（`<p align="center">`、`<details>` 徽章区等）剥离，只保留实质内容。
3. **截图**：README 中引用的仓库内图片（`assets/...`）为相对路径，需拼接为 `https://raw.githubusercontent.com/<owner>/<repo>/<分支>/<路径>` 方可外显；若用户论坛有图片转存习惯，提示用户先转存。无合适截图时可省略图片行。

## 写作要求（对照 examples/openshot.md 成品）

1. **标题**：`<项目名>：<一句话定位>`（如「OpenShot：开源的视频编辑软件」「Firemark：开源的图片/PDF 水印工具」）。中文，冒号用全角。该一级标题**同时是正文的首行**，需写在正文文件的第一行。
2. **首段简介**：`<项目名称> 是一款……` 句式开头，1-2 句话概括项目是什么、核心亮点（跨平台、免费开源、语言/技术栈），译写自 `description` 与 README 开头，不要照抄英文。
3. **`## 主要功能`**：以列表提炼 README 的核心能力，每条一行中文短句，按「平台/技术基础 → 核心能力 → 特色亮点」排序，一般 8-20 条；不要罗列命令行参数表。
4. **截图**（可选）：一张最有代表性的图片。
5. **结尾**：`---` 分隔线之后，裸 URL 形式给出开源地址（必有）与官网地址（有才写），各占一行。

正文全部使用简体中文；专有名词（项目名、技术名词）保留英文原文。

## 参考示例：Firemark

以 `https://github.com/Vitruves/firemark` 为例，按上述模板与要求整理出的成品（作为待发布临时文件保存，如 `/tmp/article.md`），其正文如下：

```markdown
# Firemark：开源的图片/PDF 水印工具

Firemark 是一款完全免费且开源的图片与 PDF 水印工具，基于 Rust 编写，支持 Linux、Mac 和 Windows 三大平台。它的目标是为个人文档提供可溯源、抗篡改的水印保护，专门对抗 AI 水印去除。

## 主要功能

- 支持跨平台运行（Linux、Mac 和 Windows），编译为单个约 5 MB 的独立二进制文件
- 基于 Rust 构建，高性能且无运行时依赖
- 支持 PNG、JPEG、PDF、WebP、TIFF 等格式，可跨格式转换输出
- 内置 17 种水印样式：斜向平铺、印章、镂空、打字机、手写签名、涂黑条、徽章、丝带、印章圈、边框等
- 借鉴钞票防伪工艺的密码学花纹（guilloche、rosette、摩尔纹等 13 种），极难用图像编辑器去除
- 专为对抗 AI 去水印设计：每次渲染输出非确定性，叠加对抗性提示注入条带，使 AI 视觉模型无法学习固定模式
- 支持自定义文字、颜色、透明度、旋转角度、位置与字体，可叠加图片水印
- 可嵌入 QR 码实现文档溯源，并支持剥离敏感元数据
- PDF 支持指定页码范围、水印置底、图层分离等选项
- 批量处理整个文件夹，支持递归、多线程与试运行，已处理文件自动跳过
- 支持 TOML 配置文件与预设（preset），如 ultra-secure（高安全）与 light（轻量）两档

![Firemark 水印效果对比](https://raw.githubusercontent.com/Vitruves/firemark/master/assets/img/paycheck-firemark-comparison.png)

---

https://github.com/Vitruves/firemark
```

标签建议：开源类项目优先匹配论坛的「开源项目」（子标签，`os_projects`）或「开源社区」标签。
