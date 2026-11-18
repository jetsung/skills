# atomcode 配置参考（TOML，`~/.atomcode/config.toml`）

官方文档：https://atomcode.atomgit.com/docs/zh/configuration.html
源码：https://atomgit.com/atomgit_atomcode/atomcode.git （`crates/atomcode-config/src/config/provider.rs`、`provider_preset.rs`、`mod.rs`）

> 配置为 **TOML**（不是 JSON）。文件顶层**没有** `deny_unknown_fields`：不认识的字段能正常加载，
> 但 atomcode 自身保存（`/provider`、`/model`、`/effort` 落盘）会重写整个文件，手写的注释会被丢弃。
> 改动后用 TUI 的 `/reload` 重新读取（或重启 atomcode）。

## 两套结构并存

| 结构 | TOML 位置 | 说明 |
|------|-----------|------|
| 旧式（legacy） | `[providers.<名>]` | 一个表 = 一个可选模型（连接 + 凭证 + 模型行为全在一起），`model` 必填 |
| 新式（v5.0.7+，推荐） | `[provider_accounts.<账号id>]` + `[models."<key>"]` | 账号（连接+凭证）与模型剖面（模型行为）分离，一个账号可挂多个模型 |

`Config::resolve_model()` 是唯一的解析边界：给定 selection id，依次解析模型剖面 → 其账号 → 账号引用的 preset → 环境变量密钥 → 旧式投影。**新式条目优先**于同 id 的旧式条目。

- `default_provider`：旧式选择 id（legacy key）；`default_model`：新式选择 id，**后者优先**
- `vision_preprocessor_provider`：图片预处理用的模型选择 id
- `[modes.*]`（模式级模型）、`evaluator_provider`（/goal 评判用的快模型）为其它可选表/字段

## 账号表 `[provider_accounts.<账号id>]`

```toml
[provider_accounts.Sense]
provider = "openai-compatible"          # preset id 或自定义协议 preset
api_key = "$SENSE_API_KEY"              # 支持 $VAR / ${VAR} / ${VAR:-默认} / 裸变量名 / 明文
base_url = "https://token.sensenova.cn/v1"
# 可选：display_name / user_agent / headers / skip_tls_verify / enterprise_url
```

`provider` 的取值来自编译期 preset 注册表（每个字段都可被账号覆盖；**未列出的厂商 id 一律回退 `openai-compatible`**，所以自定义网关永远可达）：

`deepseek`、`zhipu`、`zhipu-coding`、`openrouter`、`taotoken`、`minimax`、`minimax-token-plan`、`moonshot`、`aliyun`、`xiaomi-mimo`、`longcat`、`volcengine`、`volcengine-coding`、`siliconflow`、`deepseek-messages`、`atomgit`、`opencode`、`openai`、`anthropic`、`ollama`，加自定义协议 preset `openai-compatible`、`anthropic-compatible`、`openai-responses`。

preset 最终映射到 wire `type`（`provider_factory` 分发依据）：`openai` / `anthropic` / `deepseek-messages` / `ollama` / `responses`。`openai-compatible` 与 `anthropic-compatible` 的 base_url 必须由账号提供（preset 无默认值）。

## 模型表 `[models."<selection id>"]`

selection id（表 key）**推荐** `<account>/<model-or-alias>`，实际可为任意字符串（本机既有 `Sense/glm-5.2` 与 `AtomGit-glm5.3-flash` 两种写法都能解析）。列表展示顺序由 `model_list_order()` 决定：账号 → `rank`（无 rank 排最后）→ 模型名。

```toml
[models."Sense/glm-5.2"]
account = "Sense"                # 必填，引用账号 id
model = "glm-5.2"                # 必填，发给上游的 wire 名（可与 selection id 不同）
display_name = "GLM 5.2"
context_window = 128000          # 有默认值；max_tokens 未设时取 context_window / 4
supports_vision = true           # 显式覆盖图片输入能力；省略 = 按模型名启发式判断
# 可选：system_prompt / thinking_enabled / thinking_budget / thinking_type / thinking_keep
#       reasoning_effort / reasoning_effort_levels / reasoning_history
#       capable_model / note / retry_max_attempts / origin / rank
```

字段语义要点：

- `supports_vision`：`None` = Auto（按模型名猜 `model_name_suggests_vision`），`Some(true/false)` 权威
- `reasoning_effort`：`auto` 表示沿用 API 默认；`low|medium|high|xhigh|max` 需同时声明在 `reasoning_effort_levels` 才可切换。解析时**会被 clamp 到已声明的档位**（手写的越界值不发送）
- `reasoning_history`：`include` / `exclude`，覆盖 `reasoning_content` 历史回放策略（Kimi K2 thinking、DeepSeek V4 thinking 需 `include`）
- `capable_model`（i64 能力档位）：`task` 子代理强/弱路由用，未设置则不参与分层路由
- `note`：部署方自述模型用途，**永不推断**，缺失就显示缺失
- `origin` / `rank`：命令托管标记（`/openrouter` 写 `origin = "openrouter-free"` + OpenRouter 免费榜 `rank`）；再次运行该命令会整批替换其托管条目，而在面板里保存该模型会清掉 `origin`。**同步脚本不写这两个字段**，避免把手工条目变成命令可替换的托管条目

## api_key 解析顺序（旧式与新式一致）

1. 配置值为非空字符串：含 `$` → 展开环境变量（`$VAR`、`${VAR}`、`${VAR:-默认}`）；否则若命中同名环境变量 → 取其值；否则当字面量密钥
2. 为空/未设置/展开后为空：按 wire 类型回退 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `OLLAMA_API_KEY` / `DEEPSEEK_API_KEY` / `OPENCODE_API_KEY`，最后回退 `ATOMCODE_API_KEY`

> 本技能同步时**只写 `$VAR` 形式**（从 pi 的 `!echo -n "$VAR"` 提取变量名），不落明文密钥。

## 字段映射（pi → atomcode）

| pi 字段 | atomcode 字段 | 说明 |
|---------|---------------|------|
| `providers.<渠道>.baseUrl` | `provider_accounts.<ACC>.base_url` | 去尾斜杠 |
| `providers.<渠道>.api` | `provider_accounts.<ACC>.provider` | `openai-completions`→`openai-compatible`；`anthropic*`→`anthropic-compatible`；`openai-responses`→`openai-responses` |
| `providers.<渠道>.apiKey` `!echo -n "$VAR"` | `api_key = "$VAR"` | 解析不出变量名则不写该字段（回退环境变量） |
| `models[].id` | `model` + selection key 后缀 | key = `<ACC>/<id>` |
| `models[].name` | `display_name` | |
| `models[].contextWindow` | `context_window` | 缺失写 128000 |
| `models[].input` 含 `image` | `supports_vision = true` | 否则不写（留给 Auto） |
| `models[].maxTokens` | `max_tokens` | 一般不写，交默认 `context_window / 4` |

账号 id 命名：渠道名分段首字母大写（`amd`→`AMD` 走别名表、`agnes-com`→`AgnesCom`、`sense-ai`→`SenseAi`）；匹配已有账号优先用 **base_url 强绑定**，其次按规范化名称 + 别名表。

## 图片/决策模型

- atomcode **只有文本聊天模型概念**：`supports_vision` 表示该聊天模型能吃图片输入；不存在独立的 image 生成模型类型，也没有 pi 的 `classifier`（决策模型）——这类模型**一律不写入 atomcode**（由 `pi_cache.filter_models` 默认剔除）
- 图片预处理另有 `vision_preprocessor_provider` 指向某个已配置的聊天模型

## 同步脚本

`scripts/sync-pi-to-atomcode.py`：以 pi `~/.pi/agent/models.json` 为基准，按上表追加账号与模型段。环境无 TOML 写入库，故采用**文本级追加**——原文件逐字保留，新表头写在末尾；只增不删，已存在的 `(account, model)` 条目不覆盖（保留用户手改的 `context_window` 等）；`default_provider` / `default_model` / `vision_preprocessor_provider` 不动。执行前自动备份 `.bak-YYYYMMDD`，执行后用 `tomllib` 重新解析并断言既有内容未变。可用 `ATOMCODE_CONFIG=<路径>` 指向副本试运行。
