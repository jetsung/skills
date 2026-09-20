# CLI reference

Complete surface of the `atuin` command. The TUI is opened via `atuin search -i` or the shell's `ctrl-r` / up-arrow binding. Everything below is scriptable and non-interactive unless it explicitly says otherwise.

## Search

`atuin search [options] [QUERY]` — prefix-matches by default; append `*` or `%` for wildcards.

| Flag | Description |
|---|---|
| `--cwd` / `-c` | Restrict to a directory (default: all) |
| `--exclude-cwd` | Exclude a directory (repeatable) |
| `--exit` / `-e` | Match one exit code; repeat to add more (OR) |
| `--exclude-exit` | Exclude one exit code; repeat to add more |
| `--before` / `--after` | Time window (parsed by the `interim` crate — human strings work) |
| `--interactive` / `-i` | Open the interactive TUI |
| `--human` | Human-readable time/duration |
| `--limit` / `--offset` | Slice the result set |
| `--reverse` | Oldest first |
| `--delete` | Delete matching entries (requires query or filter) |
| `--delete-it-all` | Delete every local entry (no query allowed) |
| `--format` / `-f` | Template: `{command} {directory} {duration} {user} {host} {time} {exit} {relativetime}` |
| `--inline-height` | Max TUI height |

Examples:

```sh
atuin search -i atuin
atuin search --exit 0 --after "yesterday 3pm" cargo
atuin search --exit 1 --exit 2
atuin search --exclude-exit 0 --cwd . --before 01/04/2021
atuin search --limit 1 --reverse cargo
atuin search --delete --exit 0 --after "yesterday 3pm" cargo
```

When both `--exit` and `--exclude-exit` are set, results must match one of the included codes AND none of the excluded codes.

## History list

`atuin history list` — plain text dump, useful for scripting.

| Flag | Description |
|---|---|
| `--cwd` / `-c` | Only current directory |
| `--session` / `-s` | Only current session |
| `--human` | Human-readable time/duration |
| `--cmd-only` | Print just the command text |
| `--reverse` | Oldest first |
| `--format` | Template: `{command} {directory} {duration} {user} {host} {time}` |
| `--print0` | Null-terminated output for multiline commands |

## History prune

`atuin history prune` — delete existing entries that now match `history_filter` or `cwd_filter`. `--dry-run` previews.

## History dedup

`atuin history dedup --before <date> --dupkeep <n> [--dry-run]` — `--before` is required. Keeps the N most recent copies of each duplicate (same command + cwd + host).

## Stats

`atuin stats [period]` — period keywords: `all`, `today`, `week`, `month`, `year`. Anything else is parsed as a date and treated as a 24h window starting at that moment.

```sh
atuin stats last friday
atuin stats "last thursday 3pm"   # 24h from 3pm that day
atuin stats 01/04/22
```

Output is most-used command, total commands, unique commands.

## Import

`atuin import <shell|auto>` — supported shells: `bash`, `zsh`, `fish`, `nu`, `xonsh`, `mcfly`, `replxx`, `resh`. `auto` picks based on `$SHELL`. The original shell history file is not modified.

## Init

`atuin init <zsh|bash|fish|nu|xonsh|powershell>` — prints the shell plugin. Belongs in your rc file, not on the command line.

Flags: `--disable-up-arrow`, `--disable-ctrl-r`, `--disable-ai`. Env: `ATUIN_NOBIND=1` disables all bindings; `ATUIN_NO_BUILTIN_PREEXEC=1` stops bash-preexec auto-load.

Widget names (>= 18.0): `atuin-search`, `atuin-up-search` (zsh).

## Gen-completions

`atuin gen-completions --shell <bash|fish|zsh|nu|powershell|elvish>` — write to your shell's completion dir.

## Config

```sh
atuin config get <key> [--resolved] [--verbose]
atuin config set <key> <value> [--type auto|string|boolean|integer|float]
atuin config print [key]
```

`set` is scalar-only. For a table key it errors with a hint to use a dotted key. `--resolved` merges defaults + file + env. `--verbose` prints both.

## Sync / account

```sh
atuin register -u <u> -e <email> [-p <pass>]
atuin login    -u <u> [-p <pass>] [-k <key>]
atuin logout
atuin sync [-f]              # -f forces full sync
atuin key                    # print the encryption key
atuin account delete         # server-side only; local untouched
```

Omit `-p` / `-k` to read from stdin instead of the command line.

## Daemon

```sh
atuin daemon [start|stop|restart|status]
```

Managed automatically when `[daemon] autostart = true`.

## Store

Record-store diagnostics. Reach for these when sync looks broken or a machine has records encrypted with the wrong key.

```sh
atuin store status                          # per-tag/per-host counts
atuin store verify                          # every local record decrypts with current key?
atuin store purge                           # delete records that fail decrypt (current machine only)
atuin store rekey [KEY]                     # re-encrypt everything with a new key
atuin store rebuild <TAG>                   # regenerate e.g. history DB from record store
atuin store push [--tag X] [--host <uuid>] [--force] [--page N]
atuin store pull [--tag X] [--force] [--page N]
```

`push --force` clears the remote store, then uploads local. `pull --force` wipes local, then downloads. Both are destructive.

## Doctor

`atuin doctor` — dumps version, sync state, shell info, plugins, and system. Always attach this output when filing an issue.

## Info

`atuin info` — prints config file paths, env-var overrides, and version.

## Pty-proxy

`atuin pty-proxy` — experimental popup renderer that overlays the TUI over previous terminal output without clearing it. Generate a per-shell wrapper:

```sh
atuin pty-proxy init nu | save ~/.local/share/atuin/pty-proxy-init.nu   # nushell
# Source pty-proxy-init BEFORE the regular init
```

Not available on Windows or macOS terminals. zsh / bash / fish support it as Tier 1.
