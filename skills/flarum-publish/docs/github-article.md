# 从 GitHub 项目生成文章（整理为论坛格式）

用户提供一个 GitHub 项目链接（如 `https://github.com/<owner>/<repo>`）时，先按 [examples/demo.md](../examples/demo.md) 模板整理成中文文章，再走 SKILL.md 的「发布流程」发布。

## 文章模板（examples/demo.md）

```markdown
# <项目名称>：<项目的简单描述总结>

<项目名称> 是一款<项目描述>。

## 主要功能

- <项目的主要功能与用途>

![项目截图](//<图床域名>/<日期>/<文件名>)

---

<项目开源地址 URL>
<项目官网地址 URL>
```

注意：`# 标题` 一级标题**既是讨论标题，也是文章正文的首行**——正文第一行必须写 `# <标题>`（带 `# ` 前缀），发布时标题参数传给 `publish.sh` 为去掉 `# ` 前缀的同一字符串，两者内容完全一致。正文以 `# <项目名称>：<总结性定位>`（从 README 总结提炼、20 汉字以内）开头，其后才是简介段。模板末尾的开源地址/官网地址为裸 URL 各占一行，不加列表符号。

## 信息采集

0. **查重**：先检查论坛是否已存在该项目讨论（见 [SKILL.md 查重](../SKILL.md#查重)）——用仓库名（`<repo>`）搜索 `$FLARUM_URL/?q=<repo>`，已存在时向用户确认是否仍要整理发布。
1. **仓库元数据**：`GET https://api.github.com/repos/<owner>/<repo>`（可设 `GITHUB_TOKEN` 避免限流），提取 `description`、`language`、`license`、`homepage`、`topics` 等。
2. **README**：优先 `https://raw.githubusercontent.com/<owner>/<repo>/<默认分支>/README.md`（默认分支取 API 返回的 `default_branch`，可能是 `main` 或 `master`）。中国网络环境（`IS_CHINA=1`）下 raw 域名需加代理前缀 `https://filetas.asfd.cn/`。
   - 代理也可能失败（实测出现过 `CONNECT tunnel failed, response 502`）。此时改用 Contents API 直连读取原文：
     ```bash
     curl -fsSL -H "Accept: application/vnd.github.raw" \
       "https://api.github.com/repos/<owner>/<repo>/readme"
     curl -fsSL -H "Accept: application/vnd.github.raw" \
       "https://api.github.com/repos/<owner>/<repo>/contents/<path>?ref=<ref>"
     ```
   - 若仓库根目录有 README 的多语言文件（如 `README.zh-CN.md`），优先取简体中文版原文。
   - 若 README 含多语言切换链接（如 openaitx），直接取简体中文版本链接里的原文，或自行翻译英文正文。
   - HTML 片段（`<p align="center">`、`<details>` 徽章区等）剥离，只保留实质内容。
3. **截图**：README 中引用的仓库内图片（`assets/...`、`docs/...` 等）为相对路径，需拼接为 `https://raw.githubusercontent.com/<owner>/<repo>/<分支>/<路径>` 方可外显。从 README 中提取所有候选图片（`![alt](path)` 或 HTML `<img src="path">`），拼接完整 URL 后**逐张展示给用户选择**：
   - 用提问工具（如 `AskUserQuestion`）展示候选图片列表，每个选项的 `description` 中包含完整图片 URL（方便用户点击查看后自行决定选哪张）。
   - **先展示 URL、拿到用户确认，再转存**；不要未经确认就往图床传图。
   - 仅 1 张候选图片时，仍需确认是否添加（用户可能不需要图片）。
   - **图片也可能是 CDN 绝对地址**：部分仓库（如 jub0t/Concat）在 README 里直接用 jsDelivr 引用配图——`<img src="https://cdn.jsdelivr.net/gh/<owner>/<repo>@<分支>/assets/xxx.png">`。这类地址本身就是完整 URL，不必拼 raw 前缀，而且国内可直连，可直接作为候选；注意收集时要同时扫描 HTML `<img src>` 而不只是 Markdown `![]()`。
   - **README 里的图片路径可能已失效**（如 code-server 的 `./assets/screenshot-1.png` 返回 404，实际文件已挪到 `docs/assets/`）。404 时不要直接判为「无图」，改用 Contents API 探测常见目录：
     ```bash
     curl -s "https://api.github.com/repos/<owner>/<repo>/contents/docs/assets/<文件名>?ref=<分支>"
     ```
     命中后取其 `download_url`（即 raw 地址）作为候选，同时在给用户看图片时说明该图来自仓库其他目录。
   - 0 张候选图片时，跳过图片行。README 里唯一的图若是失效链接（404）或只是徽章，正文可改用项目官网的可用截图，并在选项描述中注明来源。
   - **检查大小**：用户选定后，用 `curl -sIL` 取 `content-length`（无则下载到本地临时文件用 `stat -c%s` 取字节数）。**≤1MB** 适合直接转存图床；**>1MB** 需先经 [SKILL.md 图片压缩与转存](../SKILL.md#图片压缩与转存1mb-场景) 流程压缩——尝试 `oxipng` / `rimage`，压缩后 <1MB 转存，两工具都失败则用原图 URL（不加代理前缀）。
   - 用户选定后，先转存到论坛图床再写入正文：
     ```bash
     "$SKILL_PATH/scripts/upload_image.sh" "<选中的图片 URL 或本地文件>"
     # 输出: <来源>	<图床URL>
     ```
     将返回的图床地址以 `![<alt>](<图床URL>)` 格式插入正文的 `## 主要功能` 列表之后、`---` 分隔线之前。**地址保持协议相对形式 `//host/path`，不要写成 `https://host/path` 或 `http://host/path`。** 用户明确要求保留原始地址时才用原地址。
4. **标签确定**：根据项目信息判断标签组（见 [SKILL.md 标签策略](../SKILL.md#标签策略)）：
   - 判断 AI 项目：`description` 或 `topics` 含 LLM/AI/机器学习/深度学习等关键词 → 使用 `[63, 86]`；否则默认 `[55, 57]`。
   - 追加语言标签：从步骤 1 获取的 `language` 字段对照 SKILL.md 语言映射表追加对应 tag ID。
   - 最终标签以逗号分隔的 ID 传给 `publish.sh`。

## 写作要求（对照 examples/openshot.md 成品）

1. **标题**：`<项目名>：<总结性定位>`（如「OpenShot：开源的视频编辑软件」「Firemark：开源的图片/PDF 水印工具」）。**从 README 内容中总结提炼定位**，不要直接从 GitHub API 的 `description` 字段照搬。中文，冒号用全角，整行标题（含项目名）控制在 **20 个汉字以内**，宁短勿长。**正文第一行写 `# <标题>`**（带 `# ` 前缀的一级标题），与传给 `publish.sh` 的标题参数（去掉 `# ` 前缀）完全一致。
2. **首段简介**：`<项目名称> 是一款……` 句式开头，1-2 句话概括项目是什么、核心亮点（跨平台、免费开源、语言/技术栈），译写自 `description` 与 README 开头，不要照抄英文。
3. **`## 主要功能`**：以列表提炼 README 的核心能力，每条一行中文短句，按「平台/技术基础 → 核心能力 → 特色亮点」排序，一般 8-20 条；不要罗列命令行参数表。
4. **截图**（可选）：经用户确认选定的图片，转存图床后以 `![<alt>](<图床URL>)` 格式插入 `## 主要功能` 列表之后、`---` 分隔线之前；**地址用协议相对形式 `//host/path`，不带 `http:` / `https:`**。无图则省略。
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

![Firemark 水印效果对比](//<图床域名>/<日期>/<hash>-<文件名>.png)

---

https://github.com/Vitruves/firemark
```

标签建议：开源类项目优先匹配论坛的「开源项目」（子标签，`os_projects`）或「开源社区」标签。
