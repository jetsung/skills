# MCP server

Atuin ships a built-in [MCP](https://modelcontextprotocol.io/) server so external AI tools (Claude Code, Cursor, Claude Desktop, …) can query your shell history. All tools are **read-only** — the agent can search and read output, but cannot modify or delete history.

## Start

The server runs over stdio; your MCP client launches it for you.

```sh
atuin mcp
```

## Register

Claude Code:

```sh
claude mcp add atuin -- atuin mcp
```

Generic MCP clients (Cursor, Claude Desktop, …):

```json
{
  "mcpServers": {
    "atuin": {
      "command": "atuin",
      "args": ["mcp"]
    }
  }
}
```

If the client doesn't have `atuin` on its `PATH`, use the full binary path (e.g. `~/.atuin/bin/atuin`).

## Tools

### `atuin_history`

Searches shell history using the same fuzzy matching as the TUI. Each result includes the command, when and where it ran, exit code, duration, and a history ID usable with `atuin_output`.

Search filters:

- **Filter mode** — `global` (default), `host`, `directory`, `workspace`, `session`. `directory` and `workspace` are relative to the directory your MCP client launched the server in — usually the editor's project dir.
- **Failed only** — return only non-zero exit codes.
- **Author** — filter to your own, to any agent, or to a specific agent. See `references/agent-hooks.md`.

Works without any extra setup (reads the SQLite DB directly).

### `atuin_output`

Fetches captured terminal output for a specific command identified by a history ID from `atuin_history`. Accepts a line range so the agent doesn't read a huge log to find a tail-end error.

Requires:

- The [daemon](https://docs.atuin.sh/latest/reference/daemon/) running
- pty-proxy set up (see `https://docs.atuin.sh/latest/ai/command-output/`)

Without them, the tool returns an error explaining output capture isn't enabled.

### `atuin_output_search`

Searches the captured output of every command — useful when the agent knows *what* was printed but not *which* command printed it. Terms are whole-word matched; all terms must appear.

Each result gives the command + metadata, plus output lines around each match with line numbers. Pass a history ID + line range to `atuin_output` to read more context.

Same requirements as `atuin_output`.

## Session scope caveat

The `session` filter mode only works when the MCP server is launched from inside an Atuin-enabled shell session. Most editors launch it outside one — the other filter modes still work.

## Privacy

All data stays on your machine. Nothing is uploaded by the MCP server beyond what your agent client itself does.
