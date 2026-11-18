# dsh 配置参考（`~/.dsh/profiles/<profile>/cordis.patch.yml`）

dsh（DeepSeek Harness）的模型提供方配置写在 **Cordis patch 层**：
`$DSH_HOME/profiles/<profile>/cordis.patch.yml`。`dsh web` 启动时 `<profile>` 为 `web`，
即 `~/.dsh/profiles/web/cordis.patch.yml`；**Electron 桌面版**使用专属 profile `desktop`
（`~/.dsh/profiles/desktop/cordis.patch.yml`，该 profile 由桌面应用专管，dsh CLI 拒绝把它
boot 起来，但**配置文件本身可直接读写**）。Web UI「设置 → 模型」与桌面版设置页写入的就是
各 profile 的这份文件；设置页顶部**打开配置文件**可直接打开。模型变更**下一次请求即生效，
无需重启**。

> 字段权威来源：包装在生产代码里的 `dsh-llm-pi-ai` schema（本文按本机 dsh
> **0.2.1-rc.5** 实测核对）。核对最新字段可用 `dsh --profile <名> --dump-config-schema`
> 导出全部 entry/patch 的 JSON Schema，或看生成配置目录
> <https://deepseek-harness.github.io/deepseek-harness/reference/config-catalog#deepseek-aidsh-llm-pi-ai>。

**密钥不落 patch**：provider 只保留 `apiKeyEnv`（环境变量名引用），**明文密钥不存在于本文件**，
统一存于 `$DSH_HOME/.credentials.yaml`（0600，结构 `{version, refs, records}`）。密钥在 UI 上是
**只写**的——保存后页面只回脱敏描述符，永不回显明文。

官方文档：https://deepseek-harness.github.io/deepseek-harness/guide/providers
（中文源：https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/providers.zh.md）

## 旧版迁移对照（重要）

dsh 升级后配置从 `settings.yaml` 迁到 profile patch 层，**旧格式已不再存在**（`~/.dsh/settings.yaml` 无此文件）：

| 项 | 旧（已废弃） | 新（当前） |
|----|--------------|------------|
| 文件 | `~/.dsh/settings.yaml` | `~/.dsh/profiles/<profile>/cordis.patch.yml` |
| 顶层结构 | 映射 `{llm-pi-ai: {providers: {...}}}` | **数组** `[{id: llm-pi-ai, name: ..., config: {providers: {...}}}, ...]` |
| providers 路径 | `llm-pi-ai.providers.{渠道}` | 数组项中 `id == 'llm-pi-ai'` 的 `config.providers.{渠道}` |
| 密钥 | `apiKeyEnv` 环境变量名引用，明文存 `.credentials.yaml` | 同（`apiKeyEnv` 引用；**patch 中不再出现明文 `apiKey`**） |

渠道级字段（`displayName`/`apiKeyEnv`/`api`/`baseURL`/`models`）语义不变；模型条目由旧版
仅 `id` 扩展为可选 `name`/`contextWindow`/`maxTokens`/`input`/`reasoningEfforts`/`compat`
（dsh ≥0.2.1 schema 支持，见「写入格式」）。

## 读取渠道配置

```bash
# 示例：读取 newapi 渠道的 baseURL 与密钥环境变量名
PATCH=~/.dsh/profiles/web/cordis.patch.yml
BASE_URL=$(python3 -c "
import yaml
doc = yaml.safe_load(open('$PATCH'))
e = next(x for x in doc if x.get('id') == 'llm-pi-ai')
print(e['config']['providers']['newapi']['baseURL'])")
API_KEY_VAR=$(python3 -c "
import yaml
doc = yaml.safe_load(open('$PATCH'))
e = next(x for x in doc if x.get('id') == 'llm-pi-ai')
print(e['config']['providers']['newapi']['apiKeyEnv'])")
API_KEY="${!API_KEY_VAR}"  # 按环境变量名取值
```

> 顶层是列表，**不要**按 `doc['llm-pi-ai']` 取值，必须先按 `id` 找到条目。
>
> **密钥只经由 `apiKeyEnv` 取环境变量值**；本文件没有 `apiKey` 明文字段可抄。若环境变量未设置
> （dsh 运行时报 `MISSING_CREDENTIAL`），两条路：导出该环境变量，或在「设置 → 模型」里重新存一次密钥
> （明文进 `.credentials.yaml`，patch 仍只留引用）。**不要**为了省事把明文写进 patch。

## 写入格式

`config.providers.{渠道}.models` 是 **YAML 列表**，元素为模型条目：`id` 必填，
可选 `name` / `contextWindow` / `maxTokens` / `input` / `reasoningEfforts` / `compat`
（模型条目已知字段集就是这六项，写到集合外没有意义；`api` 非枚举值、compat 未知开关
会在 schema/服务校验处被明确拒绝）。同步脚本写入 pi 原装参数子集（见下方「同步写入的字段」）：

```yaml
- id: llm-pi-ai
  name: "@deepseek-ai/dsh-llm-pi-ai"
  config:
    providers:
      {渠道}:
        displayName: {渠道显示名}
        apiKeyEnv: {环境变量名}    # 凭据引用；明文密钥不在这里（见下）
        api: openai-completions    # openai-completions | openai-responses | anthropic-messages
        baseURL: {baseUrl}         # URL 全大写
        models:
          - id: stealth/ox-alpha
            name: {渠道显示名} - Stealth OX Alpha     # 可选；选择器显示名
            contextWindow: 131072                    # 可选；上下文窗口
            maxTokens: 8192                          # 可选；最大输出，且兼作该模型请求默认上限
            input: [text, image]                     # 可选；仅视觉模型需要显式声明
          - id: another/free-model
```

### 同步写入的字段（脚本范围）

| 字段 | 来源 | 说明 |
|------|------|------|
| `id` | pi 模型 `id` | 原样保留，不加前缀 |
| `name` | `{渠道显示名} - {pi 模型名}` | 模型名已含渠道名则去重（如 amd "`AMD DeepSeek V4 Flash`" → "`AMD - DeepSeek V4 Flash`"）；省略时 dsh 按目录名再回退 id |
| `contextWindow` | pi 模型 `contextWindow` | 有值才写；缺省时继续走 dsh 目录/路由回退链 |
| `maxTokens` | pi 模型 `maxTokens` | 有值才写；**Sense 渠道（token.sensenova.*）不写**；注意：写入值兼作该模型请求级默认输出上限（dsh 语义），能力等价声明 |
| `input` | pi 模型 `input` 含 `image` 时写 `[text, image]` | 手动录入模型默认纯文本，视觉能力必须显式声明；省略/空列表继承路由 `defaultInput`（默认 `[text]`） |

**不写入的字段与原因**：

- `reasoningEfforts`：需要逐模型等级声明表（各等级 → 线上参数写法）。pi 的 `reasoning` 布尔
  只说明"支持推理"，映射不出等级表；不声明该字段时 dsh 落回端点默认行为，需要时在
  dsh「设置 → 模型」的模型选项中配置或手工 patch
- `compat`：属于端点断言（pi-ai 对不认识的 URL 按 OpenAI 本身处理，多数网关需要手动修正，
  最常用 `supportsDeveloperRole: false` 与 `maxTokensField: max_tokens`），参看下文 compat 段
- 其余路由/模型 schema 字段同上，均不由同步脚本写入

## 密钥与凭据

- **只写引用，不写明文**：provider 的凭据字段是 `apiKeyEnv`（环境变量名）。官方示例里没有任何
  明文 `apiKey:` 字段——明文一律落到 `$DSH_HOME/.credentials.yaml`，patch 只留引用
- **明文存放位置**：`$DSH_HOME/.credentials.yaml`（0600），结构 `{version, refs, records}`；
  UI 上密钥**只写**，保存后只回脱敏描述符，读不回明文
- **refs 的实测格式**（文档未写，本机核对确认）：`refs` 是 **`环境变量名 → 明文密钥`** 的映射，
  与 patch 里各 provider 的 `apiKeyEnv` 一一对应。因此补齐/更新凭据**不必走 UI**，可直接编辑这段：
  备份 → 只动 `refs` 段（值用 `yaml.safe_dump` 单标量输出，避免 `$`/`#`/`:` 破坏 YAML）→
  校验 `version`/`records` 与未涉及的键值不变 → 保持 0600。密钥值全程不回显、不打印
- **清理 patch 里残留的明文**：先确认 `refs` 已有同名环境变量键且值一致，**再**删 patch 的 `apiKey:` 行
  （顺序不能反，否则报 `MISSING_CREDENTIAL`）
- **排错 `MISSING_CREDENTIAL`**：通过模型页存储提供商密钥，或提供被引用的环境变量
  （官方文档「排错」第一条）
- **同步脚本不碰密钥**：`sync-pi-to-dsh.py` 只读写 `models`，`apiKeyEnv` 原样保留，
  不读取也不写入任何密钥值，报告中不回显密钥
- 历史遗留：非 provider 条目（如 `web-search-deepseek`）曾把明文 `apiKey:` 写进 patch，
  与渠道凭据无关；已按上述「清理」步骤把密钥迁入 refs 并删除明文行，patch 现只剩 `apiKeyEnv`

> provider 用 `displayName`/`apiKeyEnv`/`api`/`baseURL`（注意 `baseURL` 是 URL 全大写）。
> 写入时**只更新 models 列表**，保留原 provider 其它字段与其它 patch 条目不变。

## 配置结构（官方文档摘录）

- **Cordis patch 层**：顶层是 loader patch 条目数组（`- id: ...` / `name: ...` / `config: ...`），
  在 bundle 层之后应用；`config` 覆盖会**替换完整条目配置**，编辑已有条目时须保留其它 provider 与字段。
  常见条目：`llm-pi-ai`（第三方/自定义网关）、`llm-deepseek`（DeepSeek 直连）、
  `agent-default-model`（默认模型）、`web-search-deepseek`（联网搜索；旧配置可能残留明文
  `apiKey`，与渠道凭据无关，见「密钥与凭据」）
- **Provider ID 小写且永久**：请求、已保存会话、模型默认值、凭据引用都用它；重命名 = 新建 + 删除。
  **一个提供方只用一种协议**：网关两种协议并存需建两个提供方
- **模型探测**：「获取可用模型」按表单当前地址/协议/密钥调用端点列表；`openai-completions` /
  `openai-responses` 用 Bearer `GET {baseURL}/models`，`anthropic-messages` 用原生
  `GET {baseURL}/v1/models`（`x-api-key` + `anthropic-version: 2023-06-01`，单页最多 1000 不翻页）；
  目录内置路由由已安装目录作答不发网络请求；解析接受标准 `data` 数组或富信息 `models` 对象；
  **探测只回答候选元数据，不改配置**，保存/创建提供商之前不存储任何内容；失败或列表为空时
  手动填模型 id 即可（探测只是便利手段，非保证）
- **模型条目字段**（手动录入模型默认纯文本、无推理等级/容量，需要时逐字段显式声明）：
  - `id`（必填）；`name`（选择器显示名，省略时按目录名再回退 id）
  - `contextWindow` / `maxTokens`（整数 ≥1）；`maxTokens` 有特殊语义——**配置值兼作该模型的
    请求级默认输出上限**（未显式传 max_tokens 的请求按它封顶），目录/路由回退值只算能力不做请求默认
  - `input`（`[text, image]`；省略/空列表沿用目录，再回退路由 `defaultInput`，未知模态被拒绝）
  - `reasoningEfforts`：声明推理等级菜单，键为可选等级（`off/minimal/low/medium/high/xhigh/max` 中
    模型支持的子集），值为协议上 `reasoning_effort` 的写法（如 `max: xhigh` 可重命名）；仅 `off`
    可留空（= 不发送该参数），明确关闭推理的网关需配 `compat.thinkingFormat: deepseek`；
    `false` 声明非推理模型（内置模型去等级用 `modelOverrides.{id}.reasoningEfforts: false`）
  - `compat`：模型级兼容覆盖，逐字段胜出路由级；某协议不接受的开关在写入时被拒绝（非忽略）
- **路由（provider）级字段全集**（schema 22 项；必要时 `dsh --dump-config-schema` 核对）：
  - 常用：`apiKeyEnv`、`api`（`openai-completions`/`openai-responses`/`anthropic-messages` 三选一）、
    `baseURL`、`displayName`、`models`（列表整体替换路由目录；目录内置路由无列表时目录默认生效）
  - 容量回退：`defaultContextWindow`（262144）、`defaultMaxTokens`（32768）、`defaultInput`
    （`[text]`；**不可为空列表**；是回退不是覆盖，不收窄目录已声明的模态）
  - 推理：`reasoning`（会话未选等级时的默认等级，
    枚举 `off/minimal/low/medium/high/xhigh/max`）、`thinkingBudgets`（`minimal/low/medium/high` 预算）
  - 传输与超时：`transport`（`auto/sse/websocket/websocket-cached`）、`timeoutMs`、
    `websocketConnectTimeoutMs`、`streamIdleTimeoutMs`
  - 图片：`maxRequestImageBytes`（默认 20 MiB）、`requestImagePixelBudget`（默认 4194304 像素）、
    `requestImageMaxBytes`（默认 1 MiB）
  - 其余：`headers`（请求头字典；凭据仍走 `apiKeyEnv`）、`retryPolicy`（默认 normal 5 次）、
    `cacheRetention`（`none/short/long`）
  - `modelOverrides`（以模型 id 为键重塑目录模型）：**只在无 `models` 列表的目录路由上有意义**，
    与 `models` 并存、作用于手工声明路由或点名目录未描述的模型时会被拒绝（同步脚本不使用）
- **DeepSeek 特殊项**：默认思考的模型（OpenAI 兼容网关后的 DeepSeek V4）需 `compat.thinkingFormat: deepseek`
  （`off` 发送 `thinking: {type: disabled}`，其余等级额外发 `thinking: {type: enabled}`）；
  DeepSeek 自身路由模型自带 `off/low/high/max`，起始默认值由 `llm-deepseek.reasoningEffort` 控制
- **compat 开关规则**：写下的键必须给值（冒号留空被拒绝）；开关归属协议，某协议不接受的开关报错列出可用项；
  提供方可设置的开关全集见生成的 `dsh-llm-pi-ai` 配置参考（config-catalog 的 `PiAiCompatProfile`，
  26 字段：openai-completions 19 项（含 `maxTokensField`/`thinkingFormat` 等）、
  openai-responses 4 项、anthropic-messages 7 项；`supportsStrictMode` 通用，部分字段跨协议共享）
- **失败码识别**（排错时按 code 处理）：`MISSING_CREDENTIAL`（密钥引用解析为空）、
  `INVALID_CREDENTIAL`（凭据不可用）、`UNKNOWN_MODEL`（未配置模型）、`QUOTA`/`RATE_LIMIT`
  （终止性/暂时性配额区别对待）、`UNSUPPORTED_REASONING_EFFORT`（对非推理模型选了等级）、
  `UNSUPPORTED_OPTION`（如 `GenerateOptions.stop` 跨协议不保证）、`IMAGE_OFFLOAD_REQUIRED`（图片超路由上限）

```yaml
- id: llm-pi-ai
  config:
    providers:
      my-gateway:
        apiKeyEnv: GATEWAY_API_KEY
        api: openai-completions
        baseURL: https://gateway.example/v1
        reasoning: high
        compat:
          supportsDeveloperRole: false
          maxTokensField: max_tokens
        models:
          - id: my-model
          - id: vision-preview
            input: [text, image]
          - id: my-reasoner
            compat:
              thinkingFormat: deepseek
            reasoningEfforts:
              off:
              high: high
              max: max
```

> 同步脚本只更新 `config.providers.{渠道}.models` 列表（**追加新增条目**，条目含 id 与
> name/contextWindow/maxTokens/input 参数行，见「同步写入的字段」）；`apiKeyEnv`/`api`/`baseURL`/
> `compat`/`reasoning` 等已有字段不动（缺失时空值补充除外）；**已有模型条目一律不改动**。
> pi 模型条目声明了 `input` 含 `image` 时，新增模型条目会一并写入
> `input: [text, image]`（dsh 手动录入模型默认纯文本，不声明则视觉能力丢失）。
> 需要为新条目补 `reasoningEfforts`/`compat` 时在「设置 → 模型」的模型选项里配置或手工编辑 patch。

## 全量同步脚本

```bash
python3 scripts/sync-pi-to-dsh.py                  # 默认 profile: web
python3 scripts/sync-pi-to-dsh.py --profile dsh-tui  # 指定 profile（桌面版为 --profile desktop）
python3 scripts/sync-pi-to-dsh.py --dry-run          # 只打印计划
DSH_HOME=/path/to/dsh DSH_PROFILE=web python3 scripts/sync-pi-to-dsh.py
```

目标配置：`$DSH_HOME/profiles/<profile>/cordis.patch.yml`；models 条目为
id + name/contextWindow/maxTokens/input 参数行（Sense 渠道不含 maxTokens）；
密钥**只留 `apiKeyEnv` 引用**（脚本不写明文，明文归 `.credentials.yaml`）；
`reasoningEfforts`/`compat` 不在脚本范围（交由 dsh UI/手工配置）。

前提：目标 profile 的 patch 里须已有 `id: llm-pi-ai` 条目（至少一个渠道在 dsh
UI 建立过，或手工添加条目）；脚本**不做渠道自动新建**——pi 有而 dsh 无对应
provider 的渠道直接跳过并在报告中说明。

**写入方式：文本级增量插入**——先用 PyYAML 解析判断缺失项，再把缺失的模型条目
（id + 参数行，缩进与文件一致）插到对应 provider 的 `models` 段末尾，
**保留原文件注释、缩进、条目顺序**。原因：该文件是 patch 列表，含文件头注释以及
`ui-settings-general` / `agent-default-model` / `web-search-deepseek` 等无关条目（后者可能残留历史
明文 `apiKey`，脚本不触碰），`yaml.safe_dump` 整篇重写会丢注释、重排内容并破坏格式。

幂等可重复执行（无变更不写文件）；写入前自动备份 `.bak-YYYYMMDD`（覆盖写保留原 0600 权限）；
写回后重新解析做断言校验：patch 条目 id 与顺序不变、无关条目逐字节相等、provider 非 models 字段
不变（`baseURL`/`api` 仅允许空值补充）、**现有模型条目逐字段相等且仅允许在尾部追加**。密钥不回显。
