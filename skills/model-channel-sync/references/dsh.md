# dsh 配置参考（`~/.dsh/settings.yaml`）

dsh（DeepSeek Harness）的模型提供方配置在 `$DSH_HOME/settings.yaml`（即本 SKILL 所用的 `~/.dsh/settings.yaml`）的 `llm-pi-ai.providers` 段；Web UI「设置 → 模型」写入的就是这份文件。模型变更**下一次请求即生效，无需重启**。密钥本体存于 `$DSH_HOME/.credentials.yaml`，settings 只保留凭据引用。官方文档：https://deepseek-harness.github.io/deepseek-harness/guide/providers

## 读取渠道配置

若目标是 dsh，则从 `~/.dsh/settings.yaml` 读取，结构为 `llm-pi-ai.providers.{渠道}`，字段为 `displayName`、`apiKeyEnv`（环境变量名，非 `!echo` 形式）、`api`、`baseURL`、`models`：

```bash
# 示例：dsh 的 newapi
BASE_URL=$(python3 -c "import yaml;print(yaml.safe_load(open('~/.dsh/settings.yaml'))['llm-pi-ai']['providers']['newapi']['baseURL'])")
API_KEY_VAR=$(python3 -c "import yaml;print(yaml.safe_load(open('~/.dsh/settings.yaml'))['llm-pi-ai']['providers']['newapi']['apiKeyEnv'])")
API_KEY="${!API_KEY_VAR}"  # 按环境变量名取值
```

## 写入格式

`llm-pi-ai.providers.{渠道}.models` 是 **YAML 列表**，元素为**仅含 `id`**（无 name）：

```yaml
llm-pi-ai:
  providers:
    {渠道}:
      displayName: {渠道}
      apiKeyEnv: {环境变量名}   # 如 NEWAPI_API_KEY
      api: openai-completions
      baseURL: {baseUrl}
      models:
        - id: stealth/ox-alpha
        - id: another/free-model
```

> dsh 的 models 元素**只有 `id`**（不带 name），且 provider 用 `displayName`/`apiKeyEnv`/`baseURL`（注意大小写，`baseURL` 是 URL 全大写）。写入时**只更新 models 列表**，保留原 provider 的其它字段（displayName/apiKeyEnv/api/baseURL）不变，并遵循文件原有格式。

## 配置结构（官方文档摘录）

- **添加提供方**（Web UI）：内置提供方（id 如 `anthropic`、`openai`、`moonshotai`、`zai`）只需密钥；自定义提供方需**小写 Provider ID**（永久，请求/会话/凭据引用都用它，重命名=新建+删除）、基础 URL、API 协议、凭据、至少一个模型。**一个提供方只用一种协议**：`openai-completions` / `openai-responses` / `anthropic-messages`，网关两种协议并存需建两个提供方
- **模型探测**：「获取可用模型」按表单当前地址/协议/密钥调用 OpenAI 兼容 `GET /models`；失败或列表为空时手动填模型 id 即可
- **模型条目字段**（手动录入模型默认按纯文本、无推理等级，需在 settings.yaml 显式声明）：
  - `id`（必填）、`input`（`[text, image]`，省略/空列表则沿用目录或回退路由 `defaultInput`，未知模态被拒绝）
  - `reasoningEfforts`：声明推理等级菜单，值为协议上 `reasoning_effort` 的写法（如 `max: xhigh` 可重命名）；`off` 留空 = 不发送该参数；设 `reasoningEfforts: false` 去掉内置模型的等级
  - `compat`：模型级兼容覆盖，逐字段胜出路由级
- **路由（provider）级字段**：
  - `apiKeyEnv`（环境变量名）、`api`（协议）、`baseURL`、`displayName`、`models`
  - `defaultInput`：模态回退值（默认 `[text]`，是回退不是覆盖）；内置提供方无 `models` 列表，用 `modelOverrides`（以模型 id 为键）
  - `reasoning`：会话未选等级时的默认推理等级
  - `compat`：路由级默认兼容开关，最常用两项——`supportsDeveloperRole: false`（系统提示词不用 `developer` 角色，很多网关拒绝）与 `maxTokensField: max_tokens`（不用 `max_completion_tokens`）
- **DeepSeek 特殊项**：默认思考的模型（OpenAI 兼容网关后的 DeepSeek V4）需 `compat.thinkingFormat: deepseek`（`off` 发送 `thinking: {type: disabled}`，其余等级额外发 `thinking: {type: enabled}`）；DeepSeek 自身路由模型自带 `off/low/high/max`，起始默认值由 `llm-deepseek.reasoningEffort` 控制
- **compat 开关规则**：写下的键必须给值（冒号留空被拒绝）；开关归属协议，某协议不接受的开关报错列出可用项；全部开关见生成的 `dsh-llm-pi-ai` 配置参考（config-catalog 的 `PiAiCompatProfile`）

```yaml
llm-pi-ai:
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

> 同步脚本只更新 `llm-pi-ai.providers.{渠道}.models` 列表；`apiKeyEnv`/`api`/`baseURL`/`compat`/`reasoning` 等已有字段不动（缺失时空值补充除外）。上述 `input`/`reasoningEfforts`/`compat` 等模型级字段在 API 响应含对应数据时可一并写入，但须与文件原有格式一致。

## 全量同步脚本

```bash
python3 scripts/sync-pi-to-dsh.py
```

目标配置：`~/.dsh/settings.yaml`；models 格式为列表仅 `id`；apiKey 保留 `apiKeyEnv` 变量名。幂等可重复执行，自动备份+断言校验。
