# pi 配置参考（`~/.pi/agent/models.json`）

pi 的模型配置位于用户级文件 `~/.pi/agent/models.json`，结构为 `providers.{渠道}.models` 数组。官方文档：<https://pi.dev/docs/latest/models>。

**写入范围**：只写用户级 `~/.pi/agent/models.json`，禁止修改项目级配置（如 `<workspace>/.pi/agent/models.json`）。

## 渠道（provider）字段

| 字段 | 说明 |
|------|------|
| `baseUrl` | API 端点 URL，必须是真实地址（不支持环境变量占位符） |
| `api` | API 类型；OpenAI Chat Completions 为 `openai-completions` |
| `apiKey` | 可选；支持命令式引用，如 `!echo -n "$SENSE_API_KEY"`，也可用 `"$ENV_VAR"` 插值或直接写明文 |
| `headers` | 自定义请求头（支持值解析，规则同 `apiKey`） |
| `models` | 模型配置数组 |

`api` 可设在 provider 级（对该渠道所有模型生效）或 model 级（覆盖单个模型）。新增渠道默认使用 `openai-completions`。

## 模型（model）字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 模型标识，原样传递给 API |
| `name` | 否 | 可读标签，省略时显示 `id` |
| `api` | 否 | 覆盖 provider 的 API 类型 |
| `reasoning` | 否 | 是否支持扩展思考 |
| `input` | 否 | 输入类型，如 `["text"]`、`["text", "image"]` |
| `contextWindow` | 否 | 上下文窗口大小（token） |
| `maxTokens` | 否 | 最大输出 token 数 |
| `cost` | 否 | 每百万 token 计费 `{input, output, cacheRead, cacheWrite}` |

`id` 之外均可省略；本技能只写入映射声明且源模型实际提供的字段。

## 新增 Sense 渠道示例

```json
{
  "providers": {
    "sense": {
      "baseUrl": "https://token.sensenova.cn/v1",
      "api": "openai-completions",
      "apiKey": "!echo -n \"$SENSE_API_KEY\"",
      "models": [
        {
          "id": "sensenova-6.8-flash-lite",
          "name": "sensenova-6.8-flash-lite",
          "contextWindow": 131072,
          "maxTokens": 8192
        }
      ]
    }
  }
}
```

`baseUrl` 取 `<PREFIX>_BASE_URL` 实值；`apiKey` 使用 `!echo -n "$<PREFIX>_API_KEY"`；渠道显示名不存在独立字段，未指定显示名时 `name` 与 `id` 一致或按目标字段合法值处理。

## 更新已有渠道

- `providers.{渠道}.models` 按 `id` upsert：同 id 替换条目、新 id 追加，不产生重复。
- 保留同一文件内其他 provider 与其他模型，不自动删除本次未出现的手工模型。
- 渠道级字段（`baseUrl`、`api`）与本次渠道一致时无需改动；仅缺失或为空时补入。

## 写入后校验

```bash
python3 -m json.tool ~/.pi/agent/models.json > /dev/null
```

再确认渠道存在、`baseUrl` 为真实地址、`api` 为 `openai-completions`、`apiKey` 为命令式引用、`models` 中 `id` 唯一且数量与转换结果一致。pi 每次打开 `/model` 时自动重载配置，无需重启。
