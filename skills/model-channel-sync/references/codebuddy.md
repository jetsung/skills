# codebuddy 配置参考（`~/.codebuddy/models.json`）

官方文档：https://www.codebuddy.cn/docs/cli/models

## 配置结构

配置文件位置与优先级：
- **用户级**：`~/.codebuddy/models.json`（全局）
- **项目级**：`<workspace>/.codebuddy/models.json`（优先级高于用户级，同 `id` 模型覆盖用户级定义；`availableModels` 字段项目级完全覆盖、不合并）

**写入范围（重要）**：本技能只写**用户级** `~/.codebuddy/models.json`，**禁止修改项目级** `<workspace>/.codebuddy/models.json`——项目级配置优先级更高，会覆盖全局同名模型，且属于项目仓库文件，不应由同步写入。
- 合并策略 SmartMerge：同 `id` 覆盖、不同 `id` 追加；`availableModels` 过滤在所有合并完成后执行
- 支持**热重载**（变更自动检测，1 秒防抖），配置更新后自动同步，编辑后无需重启

顶层结构：
```json
{
  "models": [
    {
      "id": "model-id",
      "name": "Model Display Name",
      "vendor": "vendor-name",
      "apiKey": "${ENV_VAR_NAME}",
      "maxInputTokens": 200000,
      "maxOutputTokens": 8192,
      "url": "https://api.example.com/v1/chat/completions",
      "temperature": 0.7,
      "supportsToolCall": true,
      "supportsImages": true,
      "supportsReasoning": true,
      "relatedModels": {
        "lite": "model-id-lite",
        "reasoning": "model-id-reasoning"
      }
    }
  ],
  "availableModels": ["model-id-1", "model-id-2"]
}
```

`models` 数组元素（LanguageModel）字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✓ | 模型唯一标识符 |
| `name` | string | — | 模型显示名称 |
| `vendor` | string | — | 模型供应商（如 OpenAI, Google） |
| `apiKey` | string | — | API 密钥，支持环境变量引用 `${VAR_NAME}` |
| `maxInputTokens` | number | — | 最大输入 token 数 |
| `maxOutputTokens` | number | — | 最大输出 token 数 |
| `url` | string | — | API 端点，支持 `${VAR}` 引用，**必须是完整路径**（一般以 `/chat/completions` 结尾，如 `https://api.openai.com/v1/chat/completions`；只写 `https://api.openai.com/v1` 是错的） |
| `temperature` | number | — | 采样温度 0-2 |
| `supportsToolCall` | boolean | — | 是否支持工具调用 |
| `supportsImages` | boolean | — | 是否支持图片输入 |
| `supportsReasoning` | boolean | — | 是否支持推理模式 |
| `relatedModels` | object | — | 场景关联模型：`lite`/`reasoning` 已生效；`subagent`/`vision`/`longContext` 预留未启用 |

`availableModels`（`Array<string>`）：控制下拉列表显示哪些模型 id；未配置或为空则显示全部。通过 `models.json` 添加的模型自动带 `custom` 标签。

**环境变量引用（可选）**：`apiKey` 和 `url` 支持 `${VAR_NAME}` 语法，CLI 启动时解析；变量不存在则保留原始占位符（导致 API 调用失败）。建议文件权限 `600`，勿提交含明文密钥的文件到版本库——同步脚本不采用 `${VAR}` 而是写死明文实值（与 qoder 一致），因此该文件切勿提交到版本库。

**relatedModels 回退规则**：自定义模型**不继承**内置 `defaultRelatedModels`；主模型未声明 `relatedModels` 且无环境变量/`variantModels` 覆盖时，`lite`/`reasoning` 回退到主模型。场景变体解析优先级（高→低）：环境变量（`CODEBUDDY_SMALL_FAST_MODEL`=lite、`CODEBUDDY_BIG_SLOW_MODEL`=reasoning）→ 项目级 `variantModels[variant]`（存于 `settings.json`）→ 用户级 `variantModels[variant]` → 主模型条目 `relatedModels[variant]` → 内置 `defaultRelatedModels[variant]`（仅内置模型）→ 主模型自身。

## 同步专属规则（`sync-pi-to-codebuddy.py`）

- 结构与其它平台根本不同：**无渠道层级**，`models` 是扁平数组，每个模型是独立条目（`id`/`name`/`vendor`/`url`/`apiKey`/`supportsToolCall`/`supportsImages`/`supportsReasoning`/`useCustomProtocol`）
- **name 格式**：统一为 **`{vendor} - {模型名}`**（如 `Sense - DeepSeek V4 Flash`、`OpenRouter - Inkling Small (Free)`）；pi 模型 name 本身已带渠道前缀时先去掉该前缀再拼接，避免 `AMD - AMD DeepSeek...` 式重复（正则 `^{vendor}[\s\-]*` 忽略大小写匹配后剔除）
- **展开规则**：pi 每个渠道的每个模型 → 一条 codebuddy 条目；`vendor` = 渠道显示名；`url` = 渠道 baseUrl 规范化（去尾斜杠；若已以 `/chat/completions` 结尾则原样保留，否则拼接 `/chat/completions`，文档要求 url 必须含完整路径）
- **apiKey 明文实值**：从 pi 的 `!echo -n "$VAR"` 解析环境变量后**写死实值**（与 qoder 一致，不写 `${VAR}` 变量引用）；env 未设置则密钥空缺并在报告注明
- **现有条目 apiKey 规范化为明文**：`${VAR}` 变量引用条目按条目内变量名解析后转换为明文实值；已是明文的保留不动。其它字段（url/vendor/name/supports*）以 pi 为权威值；现有条目的额外字段（如 `maxInputTokens`/`maxOutputTokens`）保留
- **同模型多渠道去重**：codebuddy 扁平数组中 `id` 必须唯一；同模型在 pi 多渠道重复出现时按渠道优先级（sense/amd 最高，openrouter/kilo 最低）只保留一条
- **手工条目原样保留**（pi 中无对应的条目不删，只增不删）
- 能力字段：`supportsImages` = pi 模型 input 含 `image` 或 id 名含 vision/vl；`supportsReasoning` = pi 模型 `reasoning` 为 true；`supportsToolCall` 默认 true；`useCustomProtocol` 默认 false

## 全量同步脚本

```bash
python3 scripts/sync-pi-to-codebuddy.py
```

目标配置：`~/.codebuddy/models.json`（扁平 models 数组，每模型独立条目，含 id/name/vendor/url/apiKey/supports*）；apiKey **写死明文实值**（从 pi 的 `!echo -n "$VAR"` 解析环境变量后写实值，与 qoder 一致；现有 `${VAR}` 条目一并转换为明文）。幂等可重复执行，自动备份+断言校验。
