---
name: huawei-deveco-studio-fetch
description: '提取华为 DevEco Studio 下载地址与 SHA-256。当用户需要从华为开发者联盟下载中心（developer.huawei.com/consumer/cn/download）获取 DevEco Studio / Command Line Tools 的签名下载链接与 SHA-256 校验值时使用，尤其是不真正下载、只读取响应头 x-amz-content-sha256 的场景。触发示例：①“提取华为 DevEco 下载地址与 SHA-256”；②“获取 DevEco Studio Mac 版下载链接和校验和”；③“huawei-deveco-studio-fetch”；④“下载中心最新版的签名 URL 和 sha256”。仅在与 chrome-devtools MCP 配合、浏览器以真正 headless 模式运行时使用。'
license: MIT
---

# 提取华为 DevEco 下载地址与 SHA-256

## 用途

从 `https://developer.huawei.com/consumer/cn/download/` 的「最新版本」区块中，按**卡片顺序**提取以下四项的**下载地址**和**对应 SHA-256**：

页面 latest-card 顺序（从快照确认）：
1. **DevEco Studio 6.1.1 Release**（第 1 个卡片）→ 取 **Mac (X86)**
   - 包名：`DevEco Studio for Mac(x86) 6.1.1.300(3.6GB)`
2. **DevEco Studio 26.0.0 Beta2**（第 2 个卡片）→ 取 **Mac (X86)**
   - 包名：`DevEco Studio for Mac(x86) 26.0.0.621(3.8GB)`
3. **Command Line Tools 6.1.1 Release**（第 4 个卡片）→ 取 **Linux (X86)**
   - 包名：`Command Line Tools for Linux(x86) 6.1.1.300(2.0GB)`
4. **Command Line Tools 26.0.0 Beta2**（第 5 个卡片）→ 取 **Linux (X86)**
   - 包名：`Command Line Tools for Linux(x86) 26.0.0.621(2.2GB)`

> 说明：页面上的「SHA-256」仅提供复制按钮，哈希值不以明文渲染在 DOM 中。因此通过**触发该包的下载请求、读取响应头 `x-amz-content-sha256`** 来获取真实的文件内容 SHA-256。

## 前置条件

- 已连接 `chrome-devtools` MCP（工具名形如 `mcp__chrome-devtools__*`）。
- **浏览器必须以「真正 headless」模式运行**，否则点击下载图标会弹出「另存为 / 下载确认」对话框，需要人工取消。
  - 在 `.mcp.json` 的 `chrome-devtools` 启动参数中需包含 `--headless=new`（推荐同时加 `--disable-download-bubble --disable-features=DownloadBubble,DownloadBubbleV2` 进一步抑制下载气泡）。
  - 若未真正 headless，本 skill 会触发下载对话框且无法被 `handle_dialog` 抑制（对浏览器原生下载无效），必须改为 headless 后才能无人值守运行。
  - 修改 `.mcp.json` 后需**重启 MCP**（Disable→Enable 或重进会话）才会生效，已在运行的实例不会热加载。
- 在 headless 下，导航到 `application/zip` 会被 `net::ERR_ABORTED` 中止，文件不落盘，但请求进入网络面板，`get_network_request` 仍可读取 `x-amz-content-sha256`。
- 若目标页需要登录，需用户先在浏览器中完成登录（本 skill 不处理凭据输入）。

## 执行步骤

### 1. 打开下载页

使用 `mcp__chrome-devtools__navigate_page`：

```json
{ "type": "url", "url": "https://developer.huawei.com/consumer/cn/download/" }
```

页面加载后若被重定向到登录页，提示用户先登录，登录完成后再继续。

### 2. 捕获四个包的签名下载 URL（不拦截 window.open，靠 headless 天然中止）

> **机制（已端到端实测验证）**：
> 下载图标是 `<i nztype="Doc:download">`，位于每个 `package-item` 的 `.package-name` 行内。点击后 Angular 流程**调用 `window.open(签名URL)`**，签名 URL 形如
> `https://contentcenter-vali-drcn.dbankcdn.cn/pvt_2/.../devecostudio-mac-6.1.1.300.zip?HW-CC-KV=V1&HW-CC-Date=...&HW-CC-Expire=...&HW-CC-Sign=...`。
> - `handle_dialog(dismiss)` 只对 JS 对话框有效、**对浏览器下载本身无效**，不可依赖。
> - **不要拦截 `window.open` 返回 null**——否则签名 URL 永不请求，`get_network_request` 无数据可读（最常见失败原因）。
> - **关键坑**：headless 下 `window.open` 会在「独立的新标签 page」里发起请求，而 `list_network_requests` 只看**当前页**，所以直接去网络面板翻页往往**找不到** zip 请求。
> - **正确做法**：点击前 patch `window.open`，仅**记录**签名 URL 到 `window.__captured` 并仍放行（`return orig.call(window, u)`）；然后对每个捕获到的 URL 用 `mcp__chrome-devtools__navigate_page` **在当前页导航到该 URL**。导航到 `application/zip` 会被 `net::ERR_ABORTED` 中止（文件不落盘），但请求会进入**当前页**网络面板，从而能用 `get_network_request` 读到 `x-amz-content-sha256`。此机制已用 reqid=161/162/163/164 四次实测确认。
> - 每个 `package-item` 内有两个 `Doc:download` 图标：**第一个**（`querySelectorAll('[nztype="Doc:download"]')[0]`，在 `.package-name` 行）是下载 zip 本体；**第二个**（在 SHA-256/PGP 行）是下载 `.asc` 签名文件。务必取 `[0]`。

**2.1 先注入 window.open 捕获器（一次即可，内置去重避免重复记录）：**
```js
() => {
  window.__captured = [];
  const seen = new Set();
  const orig = window.open;
  window.open = function (u) {
    u = String(u);
    if (!seen.has(u)) { seen.add(u); window.__captured.push(u); }
    try { return orig.call(window, u); } catch (e) { return null; }
  };
  window.__capturedReady = true;
  return 'OPEN_CAPTURER_READY';
}
```

**2.2 逐个点击四个下载图标并捕获签名 URL（⚠️ 必须逐个顺序点击，不能一次性批量）**

> **实测踩坑（重要）**：一次性对 4 个图标 `dispatchEvent(click)` 会失败——Angular 的 `.package-name` 带 `disable` 类且状态会闪烁，批量点击时后 3 个常处于 `disable` 态不触发；且同一批次内多个 `window.open` 会被 headless 弹窗拦截器拦掉。结果是只捕获到 1 个 URL。
> **正确做法**：逐个顺序点击，**每次点击前等待该 `.package-name` 非 `disable`**，点击后立即确认 `window.__captured` 新增了条目，再点下一个。下方函数已内嵌该逻辑（`async` 函数 + 轮询等待 enabled）。
```js
async () => {
  const map = [
    ['DevEco Studio for Mac(x86) 6.1.1.300', 'DEVECO_REL_MACX86'],
    ['DevEco Studio for Mac(x86) 26.0.0.621', 'DEVECO_BETA_MACX86'],
    ['Command Line Tools for Linux(x86) 6.1.1.300', 'CLT_REL_LINUX_X86'],
    ['Command Line Tools for Linux(x86) 26.0.0.621', 'CLT_BETA_LINUX_X86']
  ];
  const items = Array.from(document.querySelectorAll('.package-item'));
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const result = [];
  for (const [needle, tag] of map) {
    let item = null, guard = 0;
    while (guard++ < 30) {
      item = items.find(it => (it.textContent || '').replace(/\s+/g,' ').includes(needle));
      if (item && !item.querySelector('.package-name').classList.contains('disable')) break;
      await wait(100);
    }
    if (!item) { result.push(tag + ':NO_ITEM'); continue; }
    const dls = item.querySelectorAll('[nztype="Doc:download"]');
    const dl = dls[0] || item.querySelector('i');
    if (!dl) { result.push(tag + ':NO_DL'); continue; }
    const lenBefore = window.__captured.length;
    dl.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window}));
    let g2 = 0;
    while (g2++ < 20 && window.__captured.length === lenBefore) { await wait(100); }
    result.push(tag + ':CLICKED(captured+' + (window.__captured.length - lenBefore) + ')');
    await wait(200);
  }
  return result;
}
```

**2.3 读取捕获到的 4 个（去重后）签名 URL：**
```js
() => Array.from(new Set(window.__captured))
```

> 若某一项缺失（如 NO_ITEM / 捕获为空），先 `take_snapshot` 确认页面当前包名文案，再据实调整 2.2 的匹配字符串。

### 3. 逐个导航到签名 URL 并读取 SHA-256

对去重后的每个 zip 签名 URL，用 `mcp__chrome-devtools__navigate_page` 在当前页打开：
```json
{ "type": "url", "url": "<签名URL>" }
```
（会返回 `net::ERR_ABORTED`，属正常——文件未落盘。）

随后 `list_network_requests`（pageSize=200，resourceTypes 含 `other`/`document`）会显示该 zip 请求（reqid 递增），再用 `mcp__chrome-devtools__get_network_request` 读取其响应头，提取：
- `x-amz-content-sha256` → 即 SHA-256
- 完整请求 URL（带 `HW-CC-Sign` 签名） → 即下载地址
- `content-length` / `content-type` / `etag` → 文件大小、类型、校验（用于核对）

四个文件名分别为：

- `devecostudio-mac-6.1.1.300.zip`（第1卡片 Release）
- `devecostudio-mac-26.0.0.621.zip`（第2卡片 Beta）
- `commandline-tools-linux-x64-6.1.1.300.zip`（第4卡片 Release）
- `commandline-tools-linux-x64-26.0.0.621.zip`（第5卡片 Beta）

的 `contentcenter-vali-drcn.dbankcdn.cn` 请求，记下各自 `reqid`。

再用 `mcp__chrome-devtools__get_network_request` 读取每个请求的响应头，提取：

- `x-amz-content-sha256` → 即 SHA-256
- 完整请求 URL（带 `HW-CC-Sign` 签名） → 即下载地址
- `content-length` / `content-type` / `etag` → 文件大小、类型、校验（用于核对）

> 注意：签名 URL 有有效期（`HW-CC-Expire`）。Mac 版通常 2 小时，Linux 版可能长达 10 年，但都应尽快使用；过期后用同样方式重新点击获取。

### 4. 输出与回显（必须）

提取完成后，**必须将结果以代码块形式打印回显给用户**，不得只保存在内部或文件里而不展示。四项按卡片顺序列出，每项包含：

- **工具名 / 版本(Release 或 Beta) / 平台**
- **下载地址**（完整签名 URL，原样输出，不要省略 `HW-CC-*` 参数）
- **SHA-256**（原样输出 64 位十六进制）
- **文件信息**：文件名、大小、类型、etag

回显格式（用 ```` ``` ```` 代码块包裹，便于用户直接复制）：

```
## DevEco Studio 6.1.1 Release — Mac (X86)  [第1卡片]
下载地址: <完整签名 URL>
SHA-256 : <64位哈希>
文件     : devecostudio-mac-6.1.1.300.zip (~3.6GB, application/zip)

## DevEco Studio 26.0.0 Beta2 — Mac (X86)  [第2卡片]
下载地址: <完整签名 URL>
SHA-256 : <64位哈希>
文件     : devecostudio-mac-26.0.0.621.zip (~3.82GB, application/zip)

## Command Line Tools 6.1.1 Release — Linux (X86)  [第4卡片]
下载地址: <完整签名 URL>
SHA-256 : <64位哈希>
文件     : commandline-tools-linux-x64-6.1.1.300.zip (~2.0GB, application/zip)

## Command Line Tools 26.0.0 Beta2 — Linux (X86)  [第5卡片]
下载地址: <完整签名 URL>
SHA-256 : <64位哈希>
文件     : commandline-tools-linux-x64-26.0.0.621.zip (~2.2GB, application/zip)
```

回显后，额外用一句话说明：链接有效期（Mac 约 2 小时 / Linux 约 10 年）以及本次未真正下载文件（headless 中止）。

### 5. 保存到临时文件

回显的同时，必须将相同内容（四项下载地址 + SHA-256 + 文件信息）写入临时文件 `/tmp/deveco.txt`，便于用户后续用脚本直接读取。

- 使用 Write 工具将下方内容（与回显代码块一致）写入 `/tmp/deveco.txt`，URL 与 SHA-256 原样保存、不省略。
- 若 `/tmp/deveco.txt` 已存在则覆盖。
- 写入后在回显末尾附一行提示：`已保存至 /tmp/deveco.txt`。

`/tmp/deveco.txt` 内容模板（同回显格式，不含 Markdown 标题前缀亦可，但需含四项的地址与哈希）：

```
## DevEco Studio 6.1.1 Release — Mac (X86)
下载地址: <完整签名 URL>
SHA-256 : <64位哈希>
文件     : devecostudio-mac-6.1.1.300.zip (~3.6GB, application/zip)

## DevEco Studio 26.0.0 Beta2 — Mac (X86)
下载地址: <完整签名 URL>
SHA-256 : <64位哈希>
文件     : devecostudio-mac-26.0.0.621.zip (~3.82GB, application/zip)

## Command Line Tools 6.1.1 Release — Linux (X86)
下载地址: <完整签名 URL>
SHA-256 : <64位哈希>
文件     : commandline-tools-linux-x64-6.1.1.300.zip (~2.0GB, application/zip)

## Command Line Tools 26.0.0 Beta2 — Linux (X86)
下载地址: <完整签名 URL>
SHA-256 : <64位哈希>
文件     : commandline-tools-linux-x64-26.0.0.621.zip (~2.2GB, application/zip)
```

## 注意事项

- **必须真正 headless（前置条件见上）**：若 `.mcp.json` 未配置 `--headless=new`，点击下载图标会弹出「另存为 / 下载确认」对话框，且 `handle_dialog` 对其无效，必须人工取消。请以真正 headless 运行本 skill。
- **彻底不下载（只取 SHA）**：本 skill 不拦截 `window.open`，而是**利用 headless 环境天然中止下载**的特性。点击下载图标后，Angular 调用 `window.open(签名URL)`，浏览器对该 zip URL 发起请求（进入网络面板），响应为 `application/zip` 触发下载，但**无用户确认会被 `net::ERR_ABORTED` 中止**，文件不会写入磁盘；而 `get_network_request` 仍能读到完整响应头里的 `x-amz-content-sha256`。`handle_dialog(dismiss)` 对浏览器下载无效，因此**不要**依赖它。
- **务必不要拦截 `window.open`**：拦截（返回 null）会导致签名 URL 永不请求，网络面板看不到 zip，`get_network_request` 无数据可读——这是最常见的失败根因。
- **必须逐个顺序点击，且等待 `.package-name` 非 `disable`**：页面 Angular 渲染会使下载按钮短暂 `disable`，一次性批量点击会导致后 3 个不触发、`window.open` 被弹窗拦截，最终只捕获到 1 个 URL。逐个等待 enabled 后点击可稳定捕获全部 4 个。
- **合成 click 的可行性**：本流程落地动作是 `window.open` 而非依赖 `isTrusted` 的 blob `<a>` click，因此 `dispatchEvent(new MouseEvent('click', {...}))` 合成点击在实测中可正常触发。若某次合成点击不生效，改用 `mcp__chrome-devtools__click` 真实 CDP 点击（注意：下载图标 `<i>` 不在 a11y 快照中，无 uid，需先在页面里给它打 `id` 再用 uid 点击）。
- **选择器脆弱性**：包名中的版本号（`6.1.1.300` / `26.0.0.621`）、卡片标题会随华为发布更新而变化。执行时若 `NO_ITEM`，先 `take_snapshot` 确认页面当前文案，再更新脚本中的匹配字符串。
- **卡片序号**：第 1/2/4/5 卡片对应的是 DevEco Studio Release、DevEco Studio Beta、Command Line Tools Release、Command Line Tools Beta（按页面顺序）。若华为调整卡片顺序，以「包名文本」匹配为准，不依赖序号。
- **确认下载目录无落盘**（可选）：操作后用 `find ~/Downloads -mmin -5` 验证没有新增大文件。
- 若用户需要其它平台（Windows / Mac ARM）或更多卡片，按相同模式调整匹配字符串即可。
