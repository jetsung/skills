---
name: update-gh-action-version
description: 自动更新 GitHub Actions 工作流文件中使用的 Action 版本。使用场景：用户需要更新 GitHub Actions workflow 文件中的 action 版本，或者要求升级到最新版本。
compatibility: Requires curl, sed, and access to the GitHub API
allowed-tools: Bash(scripts/update_action.sh:*)
---

# Update GitHub Actions Versions

## Instructions

Run `scripts/update_action.sh` (relative to this skill directory) to update Action versions in workflow files.

**Parameters:**
- `dir` (optional): Target directory containing workflow files (default: `.github/workflows`)
- `action` (optional): Specific Action to update (e.g., `actions/checkout`)

**Usage examples:**

```bash
# Update all Actions in .github/workflows
scripts/update_action.sh

# Update all Actions in a specific directory
scripts/update_action.sh .test/test/

# Update only actions/checkout in a specific directory
scripts/update_action.sh .test/test/ actions/checkout
```

## How it works

1. Finds all `.yml`/`.yaml` files in the target directory
2. Queries the GitHub API for the latest release tag of each Action
3. Extracts the major version (e.g., `v4.1.0` → `v4`)
4. Uses `sed` to replace version references in the workflow files