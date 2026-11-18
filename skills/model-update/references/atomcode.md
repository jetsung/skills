# atomcode 配置参考（`~/.atomcode/config.toml`）

atomcode 的模型配置位于用户级文件 `~/.atomcode/config.toml`，格式为 **TOML**（不是 JSON/YAML）。官方文档：<https://atomcode.atomgit.com/docs/zh/configuration.html>；源码 <https://atomgit.com/atomgit_atomcode/atomcode.git>（结构定义 `crates/atomcode-config/src/config/provider.rs`、`provider_preset.rs`、`config/mod.rs`）。

**写入范围**：只写用户级 `~/.atomcode/config.toml`，禁止修改项目级配置。改动后用 TUI 的 `/reload` 重新读取（或重启 atomcode）。

## 两套结构并存

| 结构 | TOML 位置 | 说明 |
|------|-----------|------|
| 旧式（legacy） | `[providers.<名>]` | 一块表 = 一个可选模型（连接 + 凭证 + 模型行为在一起），`type` 与 `model` 必填 |
| 新式（v5.0.7+，**推荐**） | `[provider_accounts.<账号id>]` + `[models."<selection id>"]` | 账号（连接+凭证）与模型剖面（模型行为）分离，一个账号可挂多个模型 |

`Config::resolve_model()` 是唯一解析边界：selection id → 模型剖面 → 其 `account` 指向的账号 → 账号 `provider` 引用的 preset → 环境变量密钥 → 旧式投影，合成一份扁平结果供 provider 构造；**新式条目优先于同 id 的旧式条目**。`default_provider` 是旧式选择 id，`default_model` 是新式选择 id，后者优先。

顶层**没有** `deny_unknown_fields`（不认识字段仍可加载），但 atomcode 自身保存配置（`/provider`、`/model`、`/effort` 落盘）会重写整个文件、**丢弃手写注释**。

## 账号表 `[provider_accounts.<账号id>]`

```toml
[provider_accounts.Sense]
provider = "openai-compatible"           # preset id 或自定义协议 preset
api_key = "$SENSE_API_KEY"               # 支持 $VAR / ${VAR} / ${VAR:-默认} / 裸变量名 / 明文
base_url = "https://token.sensenova.cn/v1"
# 可选：display_name / user_agent / headers / skip_tls_verify / enterprise_url
```

`provider` 取值来自编译期 preset 注册表，每个字段都可被账号覆盖；**未列出的厂商 id 一律回退 `openai-compatible`**（自定义网关永远可达）：

`deepseek`、`zhipu`、`zhipu-coding`、`openrouter`、`taotoken`、`minimax`、`minimax-token-plan`、`moonshot`、`aliyun`、`xiaomi-mimo`、`longcat`、`volcengine`、`volcengine-coding`、`siliconflow`、`deepseek-messages`、`atomgit`、`opencode`、`openai`、`anthropic`、`ollama`，加自定义协议 preset `openai-compatible`、`anthropic-compatible`、`openai-responses`。

preset 最终映射为 wire `type`（provider 工厂分发依据）：`openai` / `anthropic` / `deepseek-messages` / `ollama` / `responses`。`openai-compatible` 与 `anthropic-compatible` 无默认 base_url，必须由账号提供。

## 模型表 `[models."<selection id>"]`

selection id（表 key）**推荐** `<account>/<model-or-alias>`，实际可为任意字符串（既有配置里 `Sense/glm-5.2` 与 `AtomGit-glm5.3-flash` 两种写法都能解析，因此**匹配现有条目按 `(account, model)` 而非 key 字面量**）。

```toml
[models."Sense/glm-5.2"]
account = "Sense"                # 必填，引用账号 id
model = "glm-5.2"                # 必填，发给上游的 wire 名（可与 selection id 不同）
display_name = "GLM 5.2"
context_window = 128000          # 有默认值；max_tokens 未设时取 context_window / 4
supports_vision = true           # 显式覆盖图片输入能力；省略 = 按模型名启发式判断
# 可选：system_prompt / thinking_enabled / thinking_budget / thinking_type / thinking_keep
#       reasoning_effort / reasoning_effort_levels / reasoning_history / retry_max_attempts
#       capable_model / note / origin / rank
```

字段语义要点：

- `supports_vision`：省略 = Auto（按模型名猜），`true/false` 为权威值——自定义模型名或兼容网关的 wire 名不体现模态时应显式写入
- `reasoning_effort`：`auto` 表示沿用 API 默认；`low|medium|high|xhigh|max` 需同时声明在 `reasoning_effort_levels` 才可切换。解析时会 **clamp 到已声明档位**（手写的越界值不发送）
- `reasoning_history`：`include` / `exclude`，覆盖历史 `reasoning_content` 回放策略（Kimi K2 thinking、DeepSeek V4 thinking 需 `include`）
- `capable_model`（i64）：`task` 子代理强/弱路由的能力档位，未设置则不参与分层路由
- `note`：部署方自述模型用途，**永不推断**
- `origin` / `rank`：命令托管标记与展示顺序（`/openrouter` 写 `origin = "openrouter-free"` + 免费榜 `rank`，再次运行会整批替换其托管条目）——**本技能不写这两个字段**，避免把手工条目变成命令可替换/可删除的托管条目
- 列表展示顺序统一为 账号 → `rank`（无 rank 靠后）→ 模型名

## 字段映射（上游 `/models` → atomcode）

| 上游字段 | atomcode 字段 | 说明 |
|----------|---------------|------|
| `<CHANNEL>_BASE_URL` 实值 | `provider_accounts.<ACC>.base_url` | 去尾斜杠；**必须是真实地址**（只有 `api_key` 走环境变量展开，`base_url` 按字面量解析） |
| `<CHANNEL>_API_KEY` 变量名 | `provider_accounts.<ACC>.api_key = "$<CHANNEL>_API_KEY"` | 写 `$VAR` 引用，不落明文 |
| 接口类型 | `provider_accounts.<ACC>.provider` | OpenAI Chat Completions → `openai-compatible`；Anthropic Messages → `anthropic-compatible`；Responses → `openai-responses` |
| `id` | `model` + selection key 后缀 | key = `<账号id>/<id>` |
| `name` / `display_name` | `display_name` | |
| `context_length` / `contextWindow` | `context_window` | 未知时 128000 |
| `max_tokens` / `maxTokens` | `max_tokens` | 一般不写，交默认 `context_window / 4` |
| `input` / `architecture.input_modalities` 含 `image` | `supports_vision = true` | 否则不写（留给 Auto） |

**账号 id 命名**：渠道名分段首字母大写（`sense`→`Sense`、`agnes-com`→`AgnesCom`、`sense-ai`→`SenseAi`），AMD/NVIDIA 等缩写用大写显示名。匹配已有账号**优先按 `base_url` 去尾斜杠强绑定**，其次按规范化名称。

## api_key 解析顺序（旧式与新式一致）

1. 配置值为非空字符串：含 `$` → 展开环境变量（`$VAR`、`${VAR}`、`${VAR:-默认}`）；否则若命中同名环境变量 → 取其值；否则当字面量密钥
2. 为空 / 未设置 / 展开后为空：按 wire 类型回退 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `OLLAMA_API_KEY` / `DEEPSEEK_API_KEY` / `OPENCODE_API_KEY`，最后回退 `ATOMCODE_API_KEY`

> 因此 `api_key = "$<CHANNEL>_API_KEY"` 与「留空并依赖环境变量回退」都可用；本技能显式写 `$VAR`，语义更清楚。`Debug` 输出与错误信息会脱敏密钥。

## 新增渠道（一个账号 + 一批模型）步骤

1. 若无同 `base_url` 的现有账号，追加 `[provider_accounts.<账号id>]`（`provider` / `base_url` / `api_key`）；
2. 逐个模型追加 `[models."<账号id>/<id>"]`：`account`、`model` 必填，其余按上游实际提供的字段写；
3. selection key 冲突时（同名 key 已存在）追加序号后缀，不复用已有 key；
4. 不改动 `default_provider` / `default_model` / `vision_preprocessor_provider`（用户自行选择）；
5. 写入前用 `tomllib` 解析现有文件确认合法，写入后再解析一次并核对既有段落逐字未变。

**写入方式**：环境若无 TOML 写入库（`tomlkit` / `tomli_w` 未安装，仅有只读的 `tomllib`），采用**文本级追加**——原文件逐字保留（含注释），新表头写在文件末尾；不要整文件重新序列化输出。

## 更新已有渠道

- 渠道匹配按 `base_url`（去尾斜杠）→ 账号 id 规范化名 + 别名；命中即复用该账号 id，不新建；
- 模型合并按 `(account, model)`：已存在则**整条不动**（`context_window` 等可能是用户手改，不覆盖），仅追加缺失模型；
- 只增不删：上游下架的模型不会自动移除，需清理时手动处理；
- 账号级字段（`provider` / `base_url` / `api_key`）仅缺失或为空时补入，已有值不动。

## 渠道特定规则

- **Sense 渠道**（baseUrl 主机 `token.sensenova.cn` / `token.sensenova.ai`）：模型条目不写 `max_tokens`（与 pi/omp 侧「不写 reasoning/maxTokens」同源），`context_window` 照常。
- **生图 / 决策模型不写入**：atomcode 只有文本聊天模型概念——`supports_vision` 表示图片**输入**，没有独立生图模型类型，也没有 pi 的 classifier（`output_modalities` 含 `decision`）。这类模型一律不写入 atomcode。
- 图片预处理另有 `vision_preprocessor_provider` 指向某个已配置的聊天模型。

## 写入后校验

```bash
python3 - <<'EOF'
import tomllib, os
p = os.path.expanduser('~/.atomcode/config.toml')
with open(p, 'rb') as f: c = tomllib.load(f)
print(list(c), len(c.get('models', {})))
EOF
```

再核对：

- 文件可被 `tomllib` 解析；
- `[provider_accounts.*]` 的 `base_url` 为真实地址、`provider` 为合法 preset id（未知 id 虽回退 `openai-compatible`，仍应写准确值）、`api_key` 为 `$VAR` 形式；
- `[models.*]` 每条都含 `account` 与 `model`，`account` 指向的账号存在，selection key 无重复；
- 模型条目数量 = 备份中的数量 + 本批新增数量（只增不删）；既有段落与备份逐字一致；
- `default_provider` / `default_model` / `vision_preprocessor_provider` 未被改动；
- 输出与报告中不出现明文密钥（只说「密钥以 `$VAR` 引用」）。

验证失败时保留时间戳备份、报告原因，不得宣称同步成功；必要时用备份恢复。

## 注意

- 与 atomcode 自带 `/provider` 面板共存：面板保存会重写整个文件并丢弃注释（未知字段可加载，但整文件重写时可能丢），同步后若用面板改模型需留意；
- 多模型共用账号是设计意图（同一供应商两个模型不必重复 `provider`/`base_url`/`api_key`）；
- 相关同步脚本与完整 preset/字段清单见 `model-channel-sync` 技能的 `references/atomcode.md` 与 `scripts/sync-pi-to-atomcode.py`。
