---
name: incremental-translation
description: 通用中文文档项目的增量更新与 AI 翻译工作流。包含拉取上游最新文档、对比改动、生成待翻译列表以及执行增量翻译。不绑定特定项目，通过环境变量与 deploy.sh 适配任意文档仓库。
---

# 增量翻译工作流 Skill (Incremental Translation Workflows)

本 Skill 用于自动化和规范化**任意中文文档项目**的增量更新与翻译流程。它不绑定特定
上游仓库或构建工具，而是建立在项目根目录的 `deploy.sh` 约定之上，通过环境变量适配。
同一套 skill 可复用于多个项目文档，无需修改。

## 前置约定

本 skill 假设项目根目录提供 `deploy.sh`，其遵循如下约定（arcane / ferron 等中文文档
项目均采用此结构）：

- `UPSTREAM_URL`：上游文档仓库地址（如 `https://github.com/owner/repo.git`）
- `BRANCH`：要跟踪的上游分支（默认 `main`；部分项目为 `develop-2.x` 等）
- 源文档目录（`docs`/`content`/`docs` 等）与译文目录（`docs_zh`/`content_zh`/`zh` 等）
- 上游源码克隆到 `docsite/`，再由 `deploy.sh` 复制到本地源文档目录
- 提供 `--incremental` / `--source` / `--copy` / `--config` / `--translate` 等选项

### 多项目复用

把本 skill 复制到任意项目的 `.agents/skills/` 下即可启用；运行前通过环境变量切换项目：

```bash
# 项目 A（默认目录）
cd /path/to/project-a && ./deploy.sh --incremental

# 项目 B（不同上游/分支/目录）
cd /path/to/project-b
UPSTREAM_URL=https://github.com/owner/repo-b.git BRANCH=develop \
  ./deploy.sh --incremental
```

> 若项目没有 `deploy.sh`，可参照本 skill 的「流程」自行组织等价命令；核心步骤不变。
> 其中的「翻译」环节如需进一步节省 token，可配合 `incremental-translate` skill
> （支持 `PROJECT_ROOT` 跨项目调用，详见其说明）。

## 适用场景
- 上游文档仓库有更新，需要合并上游变更并翻译最新/修改过的文档。
- 需要清理上游已删除文档的对应译文。
- 需要使用 `deploy.sh` 脚本和 `aitr` 工具进行增量更新。

---

## 增量翻译操作步骤

### 1. 执行增量更新与翻译
运行 `deploy.sh` 脚本中的增量更新选项：
```bash
./deploy.sh --incremental
```

#### `--incremental` 执行的具体流程：
1. **拉取合并上游代码** (`merge_source`)：
   - 进入 `docsite` 目录拉取 `upstream/<BRANCH>` 最新提交。
   - 更新本地 `commit.txt`（记录上游 commit，便于追溯 / 对比）。
   - 将 `docsite/` 中的源文档目录覆盖复制到本地源文档目录。
2. **处理删除的文件**：
   - 比较源文档目录下被删除的文件（记录在 `deleted_docs.txt` 中）。
   - 自动删除译文目录中对应的译文文件。
3. **识别新增与修改文件**：
   - 将新增文件（`git diff --cached --name-only --diff-filter=A 源目录`）记录在 `new_docs.txt`。
   - 将修改文件（`git diff --cached --name-only --diff-filter=M 源目录`）记录在 `modified_docs.txt`。
   - 合并生成待翻译文件列表 `translate_list.txt`，并剔除图片静态资源 (`.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`)。
4. **准备配置文件** (`merge_config`)：
   - 提取 `config.example.toml` 和 `aitr.toml` 合并生成翻译所需的 `config.toml`。
5. **执行增量翻译**：
   - 如果已安装 `aitr` 工具，将使用以下命令按列表增量翻译：
     ```bash
     aitr --input translate_list.txt --list --output translated
     ```
   - 将翻译结果增量覆盖同步至译文目录。

---

### 2. 覆盖与构建译文
翻译完成后，可调用以下命令把增量翻译成果同步回源文档目录，并用项目的构建工具预览/构建：
```bash
# 将译文复制回 docsite 文档目录（若 docsite 已存在）
./deploy.sh --copy
# 本地构建（按项目实际工具，如 zensical / hugo / pnpm build 等）
# 本地预览
```
> 构建/预览命令因项目而异：静态站点的 `hugo`、Node 文档站的 `pnpm build`、
> 或 `zensical` 等，请按项目 README 执行。

---

### 3. CLI 工具与配置文件说明

- **aitr CLI 工具安装**（若未安装）：
  ```bash
  curl -L https://fx4.cn/aitr | bash
  ```
- **配置 Providers**：
  在 `config.toml` 中需配置可用的 LLM Provider（如 Grok, OpenAI 等）：
  ```toml
  [[providers]]
  enabled = true
  name = "grok"
  api_key = "YOUR_API_KEY"
  base_url = "https://api.x.ai/v1"
  model = "grok-3"
  concurrency = 1
  rate_delay = 3.0
  ```

---

## 常用命令速查

| 目的 | 命令 |
|---|---|
| 执行完整增量流程 (拉取+对比+增量翻译) | `./deploy.sh -i` / `./deploy.sh --incremental` |
| 仅合并/更新上游源码 | `./deploy.sh -s` / `./deploy.sh --source` |
| 仅重新合并配置文件 | `./deploy.sh -g` / `./deploy.sh --config` |
| 复制最新译文到 docsite 文档目录 | `./deploy.sh -c` / `./deploy.sh --copy` |
| 执行全量翻译 | `./deploy.sh -t` 或直接运行 `aitr` |

## 与其他 skill 的关系

本 skill 负责**整体流程编排**；其中的「翻译」环节如需进一步节省 token，可配合使用
`incremental-translate` skill（段落级增量翻译，仅翻译变更段）。
