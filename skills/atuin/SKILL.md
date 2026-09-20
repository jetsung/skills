---
name: atuin
description: Install, configure, drive, sync, and troubleshoot Atuin — the shell-history tool that replaces the shell's built-in history with a SQLite database recording cwd, exit code, duration, host, and session, with optional end-to-end encrypted sync and an in-process daemon. Use when the user asks to install Atuin, set up the shell plugin, register / login / sync an account, import old history, search / filter / delete history, tune config.toml or keybindings, exclude secrets and noisy commands, install AI-agent hooks (claude-code, codex, opencode, pi), write .atuin/skills, self-host a sync server, or run `atuin doctor`.
license: MIT
compatibility: Runs anywhere a POSIX shell is available. Docs reference Atuin >= 18.18; agent-hooks and record store assume >= 18.13. `cargo`/`gh` only needed for the self-hosting path.
metadata:
  upstream: https://docs.atuin.sh
  repo: https://github.com/atuinsh/atuin
---

# Atuin

Atuin is a shell-history replacement: shell hooks write every command to SQLite with metadata (cwd, exit, duration, host, session). A TUI rebinds `ctrl-r` / up arrow to search that DB. Optionally a background daemon serves an in-memory index and enables sync; sync is envelope-encrypted with the user's key, so the server operator cannot read data.

Support matrix in the [upstream docs](https://docs.atuin.sh/latest/support/): Tier 1 shells are zsh, bash, fish. Tier 2: nushell, xonsh, PowerShell. Prebuilt binaries: Linux x86_64/arm64, macOS arm64/x86_64, Windows x86_64, WSL-2.

## Quick start

```sh
# Install binary + shell plugin
curl --proto '=https' --tlsv1.2 -LsSf https://setup.atuin.sh | sh

# Register an account (optional). Key is printed once — save it.
atuin register -u <username> -e <email>

# Import existing shell history (old file is not replaced)
atuin import auto

# Restart the shell, then press ctrl-r or up arrow
```

`--non-interactive` on the install script skips prompts (CI / Dockerfile).

### Manual install + shell plugin

If you prefer a package manager (`brew`, `pacman`, `nix profile install github:atuinsh/atuin`, `cargo install atuin --locked`, `winget`), you still have to add the shell plugin line to your rc file:

```sh
# zsh
echo 'eval "$(atuin init zsh)"' >> ~/.zshrc
# bash (best with ble.sh; falls back to bash-preexec)
echo 'eval "$(atuin init bash)"' >> ~/.bashrc
# fish — inside the is-interactive block of ~/.config/fish/config.fish
atuin init fish | source
# nushell — pre-generate, then source
atuin init nu | save ~/.local/share/atuin/init.nu
# PowerShell — append to $PROFILE
# atuin init powershell | Out-String | Invoke-Expression
```

## Everyday use

Open the TUI with `ctrl-r` or the up arrow. `enter` executes the selected command; `tab` inserts it into the prompt for editing. Inside the TUI:

| Key | Action |
|---|---|
| `ctrl-r` | Cycle **filter mode** (global / host / session / directory / workspace / session-preload) |
| `ctrl-s` | Cycle **search mode** (fuzzy / prefix / fulltext / daemon-fuzzy) |
| `ctrl-a` then `c` | Switch context to the currently selected entry (jump to that session) |
| `ctrl-o` | Open inspector on the selected entry |
| `ctrl-d` (in inspector) or `ctrl-a` then `d` | Delete the selected entry |
| `alt-#` | Replay the #th line of the current results (macOS: not supported) |

Filter modes determine **which** entries are searched; search modes determine **how** your text matches. Both are configurable in `config.toml` (`filter_mode`, `search_mode`, `search.filters`). See `references/cli.md` for the full CLI surface and `references/config.md` for every setting.

## Common jobs

**Search from the CLI** (prefix by default; add `*`/`%` for wildcards):

```sh
atuin search --exit 0 --after "yesterday 3pm" make
atuin search -i atuin                        # open the TUI preloaded
atuin search --exit 1 --exit 2               # match either code
atuin search --exclude-exit 0 --cwd .        # failed commands in cwd
atuin search --limit 1 --reverse cargo       # oldest cargo command
atuin search --format "{time} [{duration}] {command}" cargo
```

**Exclude commands from history** (see `references/excluding.md`):

```sh
 echo "cmd"                                  # leading space — honors ignorespace
```

```toml
history_filter = ["^ls$", "--password"]       # command regex (unanchored)
cwd_filter = ["^/tmp", "/node_modules/"]      # working-directory regex
# secrets_filter is on by default; refuses to record AWS/GitHub/npm/Stripe/Slack-like strings
```

`atuin history prune --dry-run` then `atuin history prune` retroactively removes entries that now match your filters.

**Delete history** (local-first; sync propagates):

```sh
atuin search --delete "^curl https://internal"    # preview first without --delete
atuin search --delete-it-all                      # wipes the local DB
atuin history dedup --before 2025-01-01 --dupkeep 1
atuin account delete                              # deletes server-side data only
```

`--delete` requires a query or filter. For a true fresh start with sync, `atuin account delete` then re-register.

**Tune config** — full reference in `references/config.md`:

```sh
atuin config get search_mode --resolved
atuin config set search_mode fuzzy
atuin config set daemon.enabled true
atuin config print daemon
```

`atuin config set` is scalar-only; edit tables/arrays by hand. `~/.config/atuin/config.toml` is the file; `ATUIN_CONFIG_DIR` overrides its parent. Data lives in `~/.local/share/atuin` (override with `ATUIN_DB_PATH`, `ATUIN_RECORD_STORE_PATH`, `ATUIN_KV__DB_PATH`, `ATUIN_SCRIPTS__DB_PATH`, `ATUIN_AI__DB_PATH`, `ATUIN_META__DB_PATH`).

**Sync**:

```sh
atuin register -u <u> -e <email>         # first machine — prints key once
atuin key                                # recover your key later (do not share)
atuin login -u <u> -k <key>              # other machines
atuin sync                               # or runs automatically
atuin sync -f                            # full sync if data looks missing
```

Omit `-p` / `-k` flags to have Atuin read the secret from stdin instead of the shell command line.

## Daemon

Enable in `config.toml`:

```toml
[daemon]
enabled = true
autostart = true
```

Gives you faster writes, background sync, `daemon-fuzzy` search, and works around ZFS/SQLite stalls. If you manage the daemon via systemd socket activation, keep `autostart = false`. See `references/daemon.md` for troubleshooting.

## AI agent hooks

Record commands run by Claude Code / Codex / opencode / pi alongside your own. Agent entries are tagged with an author and hidden from the interactive TUI by default.

```sh
atuin hook install claude-code     # writes ~/.claude/settings.json
atuin hook install codex           # writes ~/.codex/hooks.json
atuin hook install opencode        # writes ~/.config/opencode/plugins/atuin.ts
atuin hook install pi              # writes ~/.pi/agent/extensions/atuin.ts
```

Only `Bash` tool invocations are captured. Restart the agent after installing. Filter explicitly from the CLI:

```sh
atuin search --author '$all-agent' -- ''      # only agent commands
atuin search --author '$all-user' -- ''       # only your commands
atuin search --author 'claude-code' -- ''     # one agent
atuin search -- ''                            # everything (no filter)
```

Reinstalling is idempotent. Details in `references/agent-hooks.md`.

## Atuin AI skills

Distinct from this file: Atuin AI reads skill files from `.atuin/skills/<name>/SKILL.md` (project) and `~/.config/atuin/skills/<name>/SKILL.md` (global). Same frontmatter shape as this skill, plus:

- `disable-model-invocation: true` — LLM cannot discover it; only reachable via `/name` in the TUI
- `$ARGUMENTS` placeholder — filled with the argument string when invoked as `/name <args>`
- Shell substitution — inline `` !`cmd` `` or a fenced block starting with `!`
- Descriptions cut to 1024 bytes and packed under a shared budget

Do **not** copy this skill to `.atuin/skills/` unless you intentionally want Atuin AI to discover it. The two directories serve different tools: this file is for coding agents (Claude Code, Codex, …); `.atuin/skills/` is for Atuin AI.

## Troubleshooting

Run `atuin doctor` first — its output is what the maintainers will ask for. Key things to look at:

- `shell.preexec` should not be `none`. If it is, the shell is not interactive, or `atuin init <shell>` never ran. Check `echo $-` includes `i`.
- Embedded terminals (JetBrains, VS Code, Cursor, Claude Code, Docker): point their shell path at `/bin/bash -i` or `/bin/zsh -i`, or add a wrapper script. Then re-run `atuin doctor`.
- Bash + bash-preexec: known issue where `ignorespace` is only partially honored — the command is filtered from Atuin but may still land in bash history. Use ble.sh for a cleaner experience.
- macOS has no `alt-#` replay in the TUI.

**Logs** land in `~/.atuin/logs` (`search.log.*`, `daemon.log.*`), rotated daily, 4-day retention by default. `ATUIN_LOG=debug atuin search` raises verbosity for a single run.

**Sync server unreachable or self-hosting**: point `sync_address` at your own host, then see `references/self-hosting.md` for docker / systemd / k8s / Postgres-vs-SQLite setup.

## Gotchas

- **Never modify migrations in place.** Add new ones. Migrations live alongside each crate; once the DB has migrated past stable there is no down-migration.
- **Never write to the sync path without reading key handling first.** The key at `~/.local/share/atuin/key` is the recovery credential for everything on the server. Losing it loses access.
- **`atuin config set` cannot touch tables or arrays.** It will refuse on a table and give the user a dotted-key hint. For lists like `history_filter`, edit `config.toml` directly.
- **`atuin history prune` and `history_filter` are different.** Filters stop *new* entries from being recorded. `prune` deletes *existing* entries that now match. Both needed when you tighten filters.
- **`--delete-it-all` is not "start over with sync".** Every local deletion becomes a delete record that still has to sync across machines, so a fresh account (`atuin account delete` + `atuin register`) is cleaner when you truly want zero records.
- **`atuin init` skips non-interactive shells.** That is why agents in `bash -c "…"` don't get Atuin. Use `atuin hook install <agent>` for coding-agent capture, or an IDE `-i` shell override.
- **Bash-preexec + `ignorespace`.** The command won't be in Atuin but may still be in bash history. Not Atuin's fault — ble.sh fixes it.
- **The `locked-tripwire` crate fails builds** when `Cargo.lock` is refreshed without `--locked`. If a `cargo update` breaks a build, run `cargo update -p locked-tripwire --precise 0.1.1` to re-pin.
- **`daemon-fuzzy` needs a running daemon.** Setting it as `search_mode` without `enabled = true` under `[daemon]` silently falls back to `fuzzy` in non-interactive search.
- **Windows** has no syntax highlighting and no pty-proxy. Otherwise parity with Tier 1.

## Reference files

Load on demand when the task needs it — don't pre-read them all:

- `references/cli.md` — full `atuin search` / `list` / `stats` / `import` / `gen-completions` / `store` / `prune` / `dedup` CLI surface with flag tables and examples
- `references/config.md` — every key in `config.toml`, including `history_filter`, `cwd_filter`, `secrets_filter`, `filter_mode`, `search_mode`, `search.filters`, `search_mode_shell_up_key_binding`, `enter_accept`, `inline_height`, `style`, `workspaces`, `sync_address`, `sync_frequency`, `[daemon]`, `[tmux]`, `[logs]`, `[ai]`, `[sync]`, `[history]`, and score multipliers
- `references/excluding.md` — the four ways to keep commands out of history, plus secret filters and `history prune`
- `references/agent-hooks.md` — hook installation, `ATUIN_HISTORY_AUTHOR` / `ATUIN_HISTORY_AUTHOR_KIND` / `ATUIN_HISTORY_INTENT` env vars, `$all-user` / `$all-agent` filters, per-agent config file layout, verification
- `references/daemon.md` — enable, socket activation, troubleshooting, and interaction with `daemon-fuzzy`
- `references/self-hosting.md` — deploy the sync server with Docker, systemd, or Kubernetes; Postgres vs SQLite URI auto-detection; client `sync_address`
- `references/mcp.md` — Atuin's built-in MCP server for exposing history search and command output to Claude Code / Cursor / others
