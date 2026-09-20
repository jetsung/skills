# AI agent hooks

Atuin can record commands run by AI coding agents (Claude Code, Codex, opencode, pi) alongside your own shell history, tagged with an author. Agent entries are hidden from interactive search by default so they don't clutter your TUI.

## Install

```sh
atuin hook install claude-code
atuin hook install codex
atuin hook install opencode
atuin hook install pi
```

Idempotent: rerunning prints `already installed, skipping` for hooks that are already registered.

## Config files written

| Agent | Path |
|---|---|
| Claude Code | `~/.claude/settings.json` |
| Codex | `~/.codex/hooks.json` |
| opencode | `~/.config/opencode/plugins/atuin.ts` (or `$XDG_CONFIG_HOME/opencode/plugins/atuin.ts`) |
| pi | `~/.pi/agent/extensions/atuin.ts` |

Restart the agent after install.

## Lifecycle

1. **PreToolUse** — agent is about to run a Bash command. Atuin records the command, cwd, and timestamp (equivalent to `history start`).
2. **PostToolUse / PostToolUseFailure** — command finished. Atuin records exit code and duration (`history end`).

Only `Bash` tool invocations are captured. File writes, web fetches, etc. are ignored.

Agents that load extensions instead of shelling out to a hook (opencode, pi) call `atuin history start` / `end` directly.

## Filtering by author

The interactive TUI shows `$all-user` by default — everything that isn't agent-run. Use the CLI `--author` flag to override:

```sh
atuin search --author '$all-user' -- ''    # only your own
atuin search --author '$all-agent' -- ''   # any agent
atuin search --author 'claude-code' -- ''  # one specific agent
atuin search --author 'claude-code' --author 'codex' -- ''
atuin search -- ''                          # everything, no filter
```

Recognized agent names today: `claude-code`, `codex`, `copilot`, `opencode`, `pi`.

Note the `--` separator before the query — Atuin uses `--` to delimit CLI flags from the search string.

## Environment variables

Atuin sets these for every captured command; you can also set them in your own tooling:

| Var | Meaning |
|---|---|
| `ATUIN_HISTORY_AUTHOR` | Author identity (`claude`, `claude-code`, `copilot`, `codex`, `opencode`, `pi`, or any name). If the value matches a known agent name AND differs from the local username, the entry is classified as agent-run. |
| `ATUIN_HISTORY_AUTHOR_KIND` | Optional: `user` or `agent`. Explicit override of classification. |
| `ATUIN_HISTORY_INTENT` | Optional free-text intent/rationale attached to the entry. |

If `ATUIN_HISTORY_AUTHOR` isn't set, Atuin defaults to the local shell username.

## Per-agent notes

- **Claude Code.** Adds hook entries to `~/.claude/settings.json` matching `^Bash$`. Claude Code calls `atuin hook claude-code` with the event on stdin as JSON.
- **Codex.** Same shape as Claude Code, writes `~/.codex/hooks.json`.
- **opencode.** The plugin records every `bash` tool command with author `opencode` and uses the tool's description as `ATUIN_HISTORY_INTENT` when provided. Two cases where nothing is recorded:
  - Commands you **deny** at the permission prompt (plugin waits until opencode is cleared to run before opening an entry).
  - Commands you type yourself inside opencode with `!cmd` or in its terminal pane (opencode didn't run them; use Atuin's own shell integration for those).
- **pi.** The extension observes pi's tool events rather than replacing the `bash` tool, so it works alongside other extensions that replace pi's bash (sandboxes, RTK). Restart or `/reload` after install.

## Verify

```sh
atuin search --author '' -- ''              # all entries
atuin search --author '$all-agent' -- ''    # only agent entries

# Or inspect the agent's config file directly:
grep atuin ~/.claude/settings.json
grep atuin ~/.codex/hooks.json
ls ~/.config/opencode/plugins/atuin.ts
ls ~/.pi/agent/extensions/atuin.ts
```
