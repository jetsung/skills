# dsh 配置参考（`~/.dsh/profiles/<profile>/cordis.patch.yml`）

dsh（DeepSeek Harness）的模型提供方配置写在 **Cordis patch 层**：
`$DSH_HOME/profiles/<profile>/cordis.patch.yml`。常规 `dsh web` 启动时 `<profile>` 为 `web`，
即 `~/.dsh/profiles/web/cordis.patch.yml`（Web UI「设置 → 模型」写入的就是这份文件；设置页顶部
**打开配置文件**可直接打开它）。模型变更**下一次请求即生效，无需重启**。

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

渠道级字段（`displayName`/`apiKeyEnv`/`api`/`baseURL`/`models`）与模型条目 `id` 语义不变。

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

`config.providers.{渠道}.models` 是 **YAML 列表**，元素为**仅含 `id`**（无 name）：

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
          - id: another/free-model
```

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
- **模型探测**：「获取可用模型」按表单当前地址/协议/密钥调用 OpenAI 兼容 `GET /models`；
  失败或列表为空时手动填模型 id 即可（探测只是便利手段，非保证）
- **模型条目字段**（手动录入模型默认按纯文本、无推理等级，需在 patch 中显式声明）：
  - `id`（必填）、`input`（`[text, image]`；省略/空列表沿用目录，再回退路由 `defaultInput`，未知模态被拒绝）
  - `reasoningEfforts`：声明推理等级菜单，值为协议上 `reasoning_effort` 的写法（如 `max: xhigh` 可重命名）；
    `off` 留空 = 不发送该参数；内置模型去等级用 `modelOverrides.{id}.reasoningEfforts: false`
  - `compat`：模型级兼容覆盖，逐字段胜出路由级
- **路由（provider）级字段**：
  - `apiKeyEnv`、`api`、`baseURL`、`displayName`、`models`
  - `defaultInput`：模态回退值（默认 `[text]`，是回退不是覆盖）；内置提供方无 `models` 列表时用
    `modelOverrides`（以模型 id 为键）
  - `reasoning`：会话未选等级时的默认推理等级
  - `compat`：路由级默认兼容开关，最常用两项——`supportsDeveloperRole: false`（系统提示词不用
    `developer` 角色，很多网关拒绝）与 `maxTokensField: max_tokens`（不用 `max_completion_tokens`）
- **DeepSeek 特殊项**：默认思考的模型（OpenAI 兼容网关后的 DeepSeek V4）需 `compat.thinkingFormat: deepseek`
  （`off` 发送 `thinking: {type: disabled}`，其余等级额外发 `thinking: {type: enabled}`）；
  DeepSeek 自身路由模型自带 `off/low/high/max`，起始默认值由 `llm-deepseek.reasoningEffort` 控制
- **compat 开关规则**：写下的键必须给值（冒号留空被拒绝）；开关归属协议，某协议不接受的开关报错列出可用项；
  全部开关见生成的 `dsh-llm-pi-ai` 配置参考（config-catalog 的 `PiAiCompatProfile`）

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

> 同步脚本只更新 `config.providers.{渠道}.models` 列表；`apiKeyEnv`/`api`/`baseURL`/`compat`/`reasoning`
> 等已有字段不动（缺失时空值补充除外）。pi 模型条目声明了 `input` 含 `image` 时，新增模型条目会一并写入
> `input: [text, image]`（dsh 手动录入模型默认纯文本，不声明则视觉能力丢失）。

## 全量同步脚本

```bash
python3 scripts/sync-pi-to-dsh.py                  # 默认 profile: web
python3 scripts/sync-pi-to-dsh.py --profile dsh-tui  # 指定 profile
python3 scripts/sync-pi-to-dsh.py --dry-run          # 只打印计划
DSH_HOME=/path/to/dsh DSH_PROFILE=web python3 scripts/sync-pi-to-dsh.py
```

目标配置：`$DSH_HOME/profiles/<profile>/cordis.patch.yml`；models 仅 `id`；密钥**只留 `apiKeyEnv` 引用**
（脚本不写明文，明文归 `.credentials.yaml`）。

**写入方式：文本级增量插入**——先用 PyYAML 解析判断缺失项，再把 `- id: xxx` 行插到对应 provider 的
`models` 段末尾，**保留原文件注释、缩进、条目顺序**。原因：该文件是 patch 列表，含文件头注释以及
`ui-settings-general` / `agent-default-model` / `web-search-deepseek` 等无关条目（后者可能残留历史
明文 `apiKey`，脚本不触碰），`yaml.safe_dump` 整篇重写会丢注释、重排内容并破坏格式。

幂等可重复执行（无变更不写文件）；写入前自动备份 `.bak-YYYYMMDD`（覆盖写保留原 0600 权限）；
写回后重新解析做断言校验：patch 条目 id 与顺序不变、无关条目逐字节相等、provider 非 models 字段不变
（`baseURL`/`api` 仅允许空值补充）、现有模型条目不被改动或删除。密钥不回显。
