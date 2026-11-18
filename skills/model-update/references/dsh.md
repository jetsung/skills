# dsh 配置参考（`~/.dsh/profiles/<profile>/cordis.patch.yml`）

dsh（DeepSeek Harness）的模型配置位于用户级 **Cordis patch 层** `$DSH_HOME/profiles/<profile>/cordis.patch.yml`：
CLI 启动（如 `dsh web`）对应 profile `web`，Electron 桌面版对应 `desktop`。结构为 patch 条目数组，
provider 配置在 `id == 'llm-pi-ai'` 条目的 `config.providers` 下。字段权威来源是 `dsh-llm-pi-ai`
schema（核对方法：`dsh --profile <名> --dump-config-schema` 导出 JSON Schema）。官方文档：
<https://deepseek-harness.github.io/deepseek-harness/guide/providers>。

**写入范围**：只写用户级 profile patch 文件，禁止修改项目级配置。

**新增渠道前提**：patch 中须已有 `id: llm-pi-ai` 条目（通常由 dsh 设置页首次添加提供商时生成）。
目标结构以该条目现有内容为准，**目标平台格式永远是转换权威**，不得让上游字段名反向决定目标结构。

## 顶层结构

```yaml
# 顶层是 loader patch 条目数组（含文件头注释与其它无关条目，插入时保留）
- id: llm-pi-ai
  name: "@deepseek-ai/dsh-llm-pi-ai"
  config:
    providers:
      {渠道}:            # provider key，小写连字符，永久不可重命名
        displayName: {渠道显示名}
        apiKeyEnv: {PREFIX}_API_KEY   # 环境变量名引用；明文密钥绝不写入本文件
        api: openai-completions       # openai-completions | openai-responses | anthropic-messages
        baseURL: {真实 URL}
        models:
          - id: model-a
            name: {渠道显示名} - Model A
            contextWindow: 131072
            maxTokens: 8192
            input: [text, image]      # 仅视觉模型显式声明
```

模型列表在渠道条目内的 `models` 数组中（不同于 zcode 的集中规则式）。

## 渠道（provider route）字段

条目为 `config.providers.{渠道}` 下的映射。schema 中字段较多（含
`modelOverrides`/`defaultContextWindow`/`headers` 等），本技能只写以下常用字段，
已有值一律不更新（仅缺失/为空时补 `baseURL`/`api`）：

| 字段 | 说明 |
|------|------|
| `displayName` | 渠道显示名；已有值不动，缺失时补渠道名 |
| `apiKeyEnv` | 凭据引用：**环境变量名**（即 `<PREFIX>_API_KEY`）；`baseURL` 与 `apiKeyEnv` 都来自 `<PREFIX>_BASE_URL` / `<PREFIX>_API_KEY` |
| `api` | wire 协议，枚举 `openai-completions` / `openai-responses` / `anthropic-messages`；一个渠道只用一种协议 |
| `baseURL` | 真实端点 URL（注意键名 `baseURL` 的 URL 全大写） |
| `models` | 模型条目数组（见下） |

`apiKeyEnv` 的明文密钥由 dsh 存放在 `$DSH_HOME/.credentials.yaml`（0600），**patch 文件中
不出现明文密钥**；新增渠道时若引用的环境变量尚未有值，dsh 首次请求报 `MISSING_CREDENTIAL`，
需用户在 dsh「设置 → 模型」存储密钥或导出环境变量——这是正常状态，不要因此写入明文。

## 模型条目字段

`models` 数组元素：`id` 必填，可选 `name` / `contextWindow` / `maxTokens` / `input` /
`reasoningEfforts` / `compat`（模型条目已知字段集就是这六项，写到集合外没有意义）。本技能只写可靠映射出的字段：

| 字段 | 说明 |
|------|------|
| `id` | 模型标识，原样保留（不加/去掉前缀） |
| `name` | 选择器显示名，统一 **`{渠道显示名} - {模型名}`**；模型名已以渠道显示名开头（忽略大小写，与各平台同步脚本实现一致）时先去除重复前缀再拼接 |
| `contextWindow` | 上下文窗口（整数）；上游无可靠数据时不映射 |
| `maxTokens` | 最大输出（整数）；**配置值兼作该模型请求默认输出上限**（dsh 语义）；渠道特定规则中要求精简的（Sense）不写 |
| `input` | 输入类型 `[text, image]`；仅 pi 字段含 `image` 时写 `[text, image]`，其余省略 |

`reasoningEfforts` 需要"等级 → 协议取值"声明表（上游的 `reasoning` 布尔不可映射出等级表），
`compat` 属于端点断言——两者不由本技能写入，需要时在 dsh UI 的模型选项配置。上游无可靠数据的
可选字段不映射、不编造；模型缺省字段由 dsh 回退链兜底（`defaultContextWindow` 262144 /
`defaultMaxTokens` 32768 / `defaultInput` `[text]`）。

## 新增渠道步骤

1. 在 `llm-pi-ai` 条目的 `config.providers` 下追加渠道条目（常用字段同上表）；
2. 在该渠道 `models` 数组下为每个模型追加条目（`id` + 可靠参数字段）；
3. **不得**动其它渠道条目与文件头注释（patch 数组还包括 `agent-default-model`/
   `web-search-deepseek` 等无关条目）；dsh 未创建过 `llm-pi-ai` 条目时不自动新建整个条目，
   提示用户先在 dsh 设置页添加任一自定义模型 API 或手工建立条目。

## 更新已有渠道

- 在对应渠道 `models` 中按 `id` upsert：新 id 追加到列表末尾，不重复、不删除本次未出现的模型；
- 渠道级字段（`displayName`/`apiKeyEnv`/`api`/`baseURL`）已有值不动，仅缺失或为空时补入
  （`baseURL` 用 `<PREFIX>_BASE_URL` 实值，`apiKeyEnv` 用 `<PREFIX>_API_KEY` 变量名）；
- 与本次同步无关的渠道/模型保持不变。

## 写入方式与校验

patch 文件含注释与无关条目，**用文本级编辑（保留注释、缩进与条目顺序），不要用
`yaml.safe_dump` 整篇重写**。写入后校验：

```bash
python3 -c "import yaml; yaml.safe_load(open('$PATCH'))"   # YAML 可解析
```

再核对：`llm-pi-ai` 条目在数组中的位置与其它条目内容不变；渠道 `api` 为合法枚举值、
`baseURL` 为真实 URL；`models` 中 `id` 唯一且数量与转换结果一致、条目字段都在 schema 范围内；
输出中不出现明文密钥。

验证失败时保留备份、报告失败原因，不得宣称同步成功。

## 注意

- patch 文件通常为 0600 权限且可能残留密钥引用，备份同样按敏感文件处理，勿提交版本库；
- `desktop` profile 由 Electron 桌面应用专管：dsh CLI 拒绝 boot 它，但 patch 文件可直接读写，
  目标文件在 `~/.dsh/profiles/desktop/cordis.patch.yml` 时照常操作；
- 模型变更下一次请求生效，无需重启 dsh。
