# Config reference

`~/.config/atuin/config.toml`. Override the parent directory with `ATUIN_CONFIG_DIR`. Data defaults to `~/.local/share/atuin`; override individual DBs with `ATUIN_DB_PATH`, `ATUIN_RECORD_STORE_PATH`, `ATUIN_KV__DB_PATH`, `ATUIN_SCRIPTS__DB_PATH`, `ATUIN_AI__DB_PATH`, `ATUIN_META__DB_PATH`.

## Paths and identity

| Key | Default | Purpose |
|---|---|---|
| `db_path` | `~/.local/share/atuin/history.db` | History SQLite DB |
| `key_path` | `~/.local/share/atuin/key` | Encryption key |
| `dialect` | `us` | Date parsing dialect (`uk`, `us`) — affects `stats` |

## Sync

| Key | Default | Notes |
|---|---|---|
| `sync_address` | `https://api.atuin.sh` | Point at your own host to self-host |
| `sync_frequency` | `5m` | Duration string; bare integer is seconds; `0` = sync after every command |
| `auto_sync` | `true` | Turn off to sync only by hand |
| `sync_v1_enabled` | varies | Legacy V1 protocol toggle |

## Update check

`update_check = true` by default. Checks `https://api.atuin.sh` at most hourly. With `update_check = false` and no sync set up, Atuin makes no network requests.

## Search and filter

| Key | Default | Notes |
|---|---|---|
| `search_mode` | `fuzzy` | `fuzzy`, `prefix`, `fulltext`, `daemon-fuzzy` |
| `filter_mode` | `global` | `global`, `host`, `session`, `directory`, `workspace`, `session-preload` |
| `search.filters` | varies | Remove specific filter modes from the ctrl-r rotation |
| `search_mode_shell_up_key_binding` | matches `filter_mode` | Different mode for the up arrow vs. ctrl-r |
| `workspaces` | `false` | Required for the `workspace` filter mode (git-repo aware) |

### Fuzzy search syntax

`fuzzy` and `daemon-fuzzy` use fzf syntax:

| Token | Meaning |
|---|---|
| `sbtrkt` | Fuzzy match |
| `'wild` | Quoted exact match |
| `^music` | Prefix |
| `.mp3$` | Suffix |
| `!fire` | Inverse exact |
| `!^music` | Inverse prefix |
| `!.mp3$` | Inverse suffix |
| `A | B` | OR (not supported in `daemon-fuzzy`) |

### Score multipliers (`daemon-fuzzy`)

Weights for the daemon's in-memory ranking. Higher = ranked higher. Adjust to taste.

```toml
[daemon.search]
score-multiplier-frequency = 1.0
score-multiplier-recency   = 1.0
score-multiplier-frecency  = 1.0
```

## Excluding commands

- `history_filter = [...]` — regexes applied to the command string. Unanchored, so use `^…$` for whole-command matches.
- `cwd_filter = [...]` — regexes applied to the working directory path.
- `secrets_filter` — enabled by default; refuses to record commands that look like AWS/GitHub/npm/Stripe/Slack credentials. Do not disable.
- Leading space — shells honor `ignorespace` and Atuin honors that too.
- `ATUIN_NOBIND` — used with `atuin init` to skip key binding entirely.

## TUI behavior

| Key | Default | Notes |
|---|---|---|
| `enter_accept` | `true` | `false` inserts into the prompt for editing instead of executing |
| `inline_height` | `0` | Height of the inline TUI (`0` = full screen) |
| `style` | varies | e.g. `"compact"` for a denser UI |
| `ctrl_n_shortcuts` | `false` | `true` = Ctrl-0..9 replaces Alt-0..9 in the TUI (macOS without a real Alt) |
| `max_height` / `max_width` | `0` | Cap TUI dimensions |

## Theme

See the [theming guide](https://docs.atuin.sh/latest/guide/theming/). Themes live under `theme = "name"` and can be overridden with `[style.colors]`.

## `[daemon]`

```toml
[daemon]
enabled = true
autostart = true
socket_path = "/tmp/atuin_daemon.sock"
pidfile_path = "/tmp/atuin_daemon.pid"
timeout = 1000
```

`autostart = false` if you manage the daemon via systemd socket activation or `tmux`. See `references/daemon.md`.

## `[tmux]`

```toml
[tmux]
enabled = true
```

Renders the TUI in a tmux popup. Skip on iTerm2's native tmux integration (can't display tmux popups).

## `[logs]`

```toml
[logs]
enabled = true
dir = "~/.atuin/logs"
level = "info"
```

Daily rotation, 4-day retention by default. `ATUIN_LOG=debug atuin …` overrides `level` for one invocation.

## `[sync]`

```toml
[sync]
auto_import = true
```

Auto-import your shell history on first run.

## `[history]`

```toml
[history]
auto_save = true
```

Controls whether `history end` writes to the DB immediately or lets the daemon batch.

## `[ai]`

Atuin AI settings (endpoint, session timeout, enabled flag, context files). See `docs/docs/ai/settings.md` upstream.

## `[search]`

```toml
[search]
filters = ["global", "session", "host", "directory"]
```

Controls which filter modes appear in the ctrl-r rotation. Not the same as `filter_mode`.

## Shell-specific overrides

- **Bash**: `atuin init bash` auto-loads bash-preexec (>= 18.18). Disable with `ATUIN_NO_BUILTIN_PREEXEC=1`. For a cleaner ignorespace / subshell story use ble.sh (>= 0.4) instead.
- **Zsh**: `add-zsh-hook` native. Widgets: `atuin-search`, `atuin-up-search` (>= 18.0).
- **Fish**: respects `fish --private`.
- **Nushell / xonsh / PowerShell**: Tier 2. No inline popup on nushell; no pty-proxy on Windows.

## Environment variables

| Var | Effect |
|---|---|
| `ATUIN_CONFIG_DIR` | Config directory (parent of `config.toml`) |
| `ATUIN_DB_PATH` | History DB path |
| `ATUIN_RECORD_STORE_PATH` | Primary record store |
| `ATUIN_KV__DB_PATH` | KV DB |
| `ATUIN_SCRIPTS__DB_PATH` | Scripts DB |
| `ATUIN_AI__DB_PATH` | AI sessions DB |
| `ATUIN_META__DB_PATH` | Meta DB |
| `ATUIN_LOG` | Per-invocation log level override |
| `ATUIN_SESSION` | Set by Atuin; session ID |
| `ATUIN_SHLVL` | Set by Atuin; shell nesting level |
| `ATUIN_HISTORY_ID` | Set by Atuin; current command's temp ID |
| `ATUIN_HISTORY_AUTHOR` | Optional author (e.g. `claude`, `copilot`). Known agent names tag the entry as agent-run |
| `ATUIN_HISTORY_AUTHOR_KIND` | Optional: `user` or `agent` — explicit override of classification |
| `ATUIN_HISTORY_INTENT` | Optional free-text intent/rationale for the entry |
| `ATUIN_NOBIND` | Set before `atuin init` to skip all key bindings |
| `ATUIN_NO_BUILTIN_PREEXEC` | Set before `atuin init bash` to skip auto-loading bash-preexec |
