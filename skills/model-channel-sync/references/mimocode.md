# mimocode 配置参考（`~/.config/mimocode/mimocode.jsonc`）

官方 schema：https://mimo.xiaomi.com/mimocode/config.json

## 配置文件位置与优先级

| 路径 | 优先级 | 说明 |
|------|--------|------|
| `~/.config/mimocode/config.json` | 低 | 全局 |
| `~/.config/mimocode/mimocode.json` | 中 | 全局 |
| `~/.config/mimocode/mimocode.jsonc` | **高** | 全局，支持注释与尾逗号 |
| `<项目>/.mimocode/mimocode.json(c)` | 项目级 | **本技能不写** |

多文件并存时后者覆盖前者。本技能只写全局最高优先级文件（默认创建/更新 `mimocode.jsonc`）。

## 与 opencode 的关系（同步策略）

mimocode 的 `provider` 子树与 opencode **同构**（字段名 `baseURL`/`apiKey`/`models`/`npm` 一致），因此：

- **不从 pi 直接映射到 mimocode**，避免维护第二套字段转换
- 流水线：`pi → opencode`（合并式，占位符）→ `opencode → mimocode`（**provider 整块覆盖**）
- 覆盖语义：清空 mimocode 原 `provider` 后写入 opencode 的 `provider`；其余顶层字段（`mcp`/`agent`/`skills`/`command` 等）保留
- `$schema` 写为 `https://mimo.xiaomi.com/mimocode/config.json`

## 密钥必须明文（与 zcode/qoder 同级）

mimocode **不认** opencode 的 `{env:VAR}` 占位符（也不认 pi 的 `!echo -n "$VAR"`）。覆盖写入前必须把占位符解析为**环境变量明文实值**：

| 源形态（opencode/pi） | 处理 |
|----------------------|------|
| `{env:VAR}` | 解析 `os.environ[VAR]` 写明文 |
| `!echo -n "$VAR"` | 同上 |
| `"$VAR"` / `${VAR}` | 同上 |
| 已是明文 | 原样保留 |

解析优先级：**环境变量实值 > mimocode 目标已有明文 > 空字符串**（env 未设置时保留目标旧明文，避免空跑清掉密钥；两处皆无则写空并在报告注明）。运行前需在已注入密钥环境变量的 shell 中执行。

解析范围：`options.apiKey`、`options.baseURL`、`options.enterpriseUrl`、`options.headers.*`、模型级 `options`/`headers` 中的同类字段。写入后不得残留占位符（脚本有断言）。

## provider 结构（与 opencode 对齐）

```jsonc
{
  "$schema": "https://mimo.xiaomi.com/mimocode/config.json",
  "model": "custom/MODEL_ID",
  "provider": {
    "custom": {
      "name": "Custom",
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "BASE_URL",
        "apiKey": "API_KEY"
      },
      "models": {
        "MODEL_ID": {
          "id": "MODEL_ID",
          "name": "MODEL_ID",
          "family": "custom"
        }
      }
    }
  }
}
```

### 提供商级字段

| 字段 | 说明 |
|------|------|
| `npm` | 适配器包名；OpenAI 兼容用 `@ai-sdk/openai-compatible`，Anthropic Messages 用 `@ai-sdk/anthropic`。覆盖时若源缺失该字段，脚本兜底补 `@ai-sdk/openai-compatible` |
| `options.baseURL` / `options.apiKey` | 端点与密钥，**写明文实值**（占位符须先解析，见上节） |
| `models` | 对象 map：key = 模型 id（发给上游的原样 id），value = 模型条目 |
| `only_configured_models` | **mimocode 独有**：`true` 时只展示 `models` 中列出的模型 |
| `whitelist` / `blacklist` | 与 opencode 相同 |

### 模型条目差异（相对 opencode）

| 字段 | mimocode | 同步时处理 |
|------|----------|------------|
| `cachePromptTTL` | 独有（如 `"1h"`） | opencode 无此字段，覆盖后不保留 mimocode 旧值 |
| `status` 枚举 | 无 `active` | opencode 若写 `active`，覆盖时原样拷入（schema 校验可能告警，运行不受影响） |
| `modalities` | `input`/`output` 必填 | 同上，原样拷贝 |
| `limit` / `cost` | 与 opencode 一致 | 原样拷贝 |

> 覆盖式同步的取舍：以 opencode 为单一事实源，mimocode 独有扩展字段在覆盖后会丢失。需要保留时，在 opencode 源数据中补对应字段（两边 schema 都允许额外模型字段时），或覆盖后手工补。

## 写入后校验

```bash
python3 -m json.tool ~/.config/mimocode/mimocode.jsonc > /dev/null
# 或与源对比
python3 -c "import json,pathlib; a=json.load(open('$HOME/.config/opencode/opencode.json')); b=json.load(open('$HOME/.config/mimocode/mimocode.jsonc')); assert a['provider']==b['provider']; print('provider 一致')"
```

配置改动需**重启 mimocode / 新开会话**后生效。

## 同步脚本

```bash
# 完整流水线：pi → opencode → mimocode（provider 覆盖）
python3 scripts/sync-pi-to-mimocode.py

# 只做第二段：opencode → mimocode 覆盖
python3 scripts/sync-opencode-to-mimocode.py
python3 scripts/sync-opencode-to-mimocode.py --dry-run   # 只打印计划
```

自动备份（`.bak-YYYYMMDD-HHMMSS`）；断言 provider 结构与 opencode 源一致、密钥占位符已解析为明文、其余顶层字段不被改动；密钥不回显。
