# Daemon

Background process serving four jobs:

1. Batch writes to the SQLite history DB for lower command latency
2. Sync when idle (so machines are up to date when you resume)
3. Provide a hot in-memory index for `daemon-fuzzy` search mode
4. Background maintenance on the record store

Also works around ZFS / SQLite performance stalls on some hosts.

## Enable

```toml
[daemon]
enabled = true
autostart = true
```

With `autostart = true`, the CLI manages the daemon's lifecycle for you — no separate service needed. If a legacy experimental daemon is already running, `autostart` cannot upgrade it in-place; run `atuin daemon stop` once, then restart.

## Managing

```sh
atuin daemon start
atuin daemon stop
atuin daemon restart
atuin daemon status
```

If you manage the daemon yourself (systemd socket activation, tmux), keep `autostart = false` and let your process manager own the lifecycle.

## Interaction with `search_mode`

`search_mode = "daemon-fuzzy"` requires the daemon to be running. In non-interactive searches (`atuin search <query>` from the CLI), `daemon-fuzzy` silently behaves like `fuzzy` when the daemon is unreachable. In the TUI, the same fallback applies.

If you want `daemon-fuzzy` but don't want to touch the daemon, keep `search_mode = "fuzzy"` — it's identical behavior without the extra process.

## Score multipliers

Adjust the ranking in `daemon-fuzzy`:

```toml
[daemon.search]
score-multiplier-frequency = 1.5   # favor commands you've run often
score-multiplier-recency   = 1.0
score-multiplier-frecency  = 1.2   # hybrid
```

Higher value = stronger pull on that signal.

## Timeout

```toml
[daemon]
timeout = 1000
```

Milliseconds. Applies to gRPC calls the CLI makes into the daemon. Bump if you see timeout errors under load.

## Troubleshooting

Symptoms and where to look:

- **`atuin search` hangs / is slow** → check `atuin daemon status`. If the daemon is down and `autostart = false`, either start it or flip `autostart = true`.
- **`daemon-fuzzy` returns results that look like plain `fuzzy`** → the daemon isn't responding in time. Look at daemon logs (`~/.atuin/logs/daemon.log.*`), raise `timeout`.
- **Daemon refuses to start after an upgrade** → an older experimental daemon may still be running with a stale socket. `atuin daemon stop`, kill any lingering process, then start again.
- **ZFS / networked FS stalls** → the daemon's role here is to serialize writes and avoid lock contention. If writes still stall, this is a filesystem-level issue; the daemon can help but cannot fix it.

Logs: `~/.atuin/logs/daemon.log.*`, rotated daily, 4-day retention. `ATUIN_LOG=debug atuin daemon …` raises verbosity for one invocation.
