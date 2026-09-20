# Excluding commands from history

Four independent mechanisms. Use whichever fits the shape of the noise; they all compose.

## 1. Leading space (`ignorespace`)

The quickest single-command exclusion. Works if your shell honors `ignorespace` and Atuin's preexec backend sees it.

```sh
 echo "this command will not be in Atuin"
```

**Bash caveat:** with bash-preexec (not ble.sh), ignorespace is only partially honored — the command won't appear in Atuin, but it may still be written to `~/.bash_history`. ble.sh (>= 0.4) is the recommended bash preexec backend; install it and load it *before* `atuin init bash` in `~/.bashrc`.

## 2. Command regex: `history_filter`

Excludes any command whose text matches any pattern. Patterns are unanchored regexes — use `^…$` to match the whole command.

```toml
history_filter = [
    "^ls$",         # bare `ls` only; `ls -la` still recorded
    "^cd ",         # any cd
    "--password",   # anywhere in the command
]
```

## 3. Directory regex: `cwd_filter`

Excludes every command whose working directory matches. Also unanchored.

```toml
cwd_filter = [
    "^/tmp",               # nothing from /tmp
    "/node_modules/",      # nothing inside any node_modules
    "^/home/user/scratch", # a scratch dir
]
```

## 4. Skip Atuin entirely in certain shells

If a tool spawns shells you'd rather not record, guard the `atuin init` line:

```sh
# .bashrc / .zshrc
if [[ -z "${MY_TOOL_SESSION}" ]]; then
    eval "$(atuin init bash)"
fi
```

Have the tool set `MY_TOOL_SESSION=1` when it spawns a shell.

For AI agents (Claude Code, Codex, opencode, pi) you don't need to exclude them — Atuin tags agent-run commands with an author and hides them from interactive search by default. See `references/agent-hooks.md`.

## Automatic secret filtering

Independent of the above, Atuin refuses to record commands that look like credentials. On by default; covers AWS keys, GitHub/npm tokens, Slack webhooks, Stripe keys, and more. Do not disable `secrets_filter`.

## Cleaning up entries that already exist

`history_filter` and `cwd_filter` only apply going forward. To remove entries Atuin recorded *before* you added the filter:

```sh
atuin history prune --dry-run   # preview
atuin history prune             # execute
```

For entries that don't match a filter, use `atuin search --delete <query>` or the TUI inspector. See the SKILL.md "Delete history" section for the destructive options.

## Verifying

```sh
atuin doctor                # shell.preexec is not 'none'
atuin history list --cmd-only | grep '<command-that-should-not-appear>'
```

If the offending command still shows up in `history list`, the filter regex is wrong (try `^…$` if it is anchored), or the shell preexec backend is misbehaving (bash-preexec ignorespace issue — switch to ble.sh).
