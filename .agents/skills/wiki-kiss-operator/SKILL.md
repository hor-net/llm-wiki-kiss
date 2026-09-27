---
name: "wiki-kiss-operator"
description: "Handles the installation, startup and configuration of a wiki-kiss instance (MCP server + REST). Invoke when the user asks to install, start, stop, integrate or troubleshoot the wiki-kiss system."
---

# Wiki KISS — Operator

This skill explains to an AI agent (Claude Code, Claude Desktop, Open
Cloud, …) how to **install, configure and operate** a wiki-kiss instance,
including integration with MCP clients.

## When to invoke this skill

- The user asks to "install the wiki", "configure the MCP server", "start
  the REST API", "stop the services", "check the status".
- The user asks how to integrate the wiki with Claude Code, Claude
  Desktop, Open Cloud, Perplexity or another MCP-compatible client.
- The user reports a problem (for example "the server does not start",
  "the port is busy", "the tools are missing in the client").
- The user wants to add the wiki to a new client or environment.

Do not invoke when:
- The user only wants to read or write wiki content (use
  `wiki-kiss-bridge`).

## Project stack

- **Storage**: `.md`/`.html` files in a wiki folder (default `./wiki`).
- **MCP server**: Python ≥ 3.10, `mcp` SDK, stdio transport.
- **REST API**: FastAPI + Uvicorn on `127.0.0.1:8765` (default).
- **Wrappers**: shell scripts in `scripts/`.

## Installation

From inside the project folder:

```bash
# Install, choose the root, generate the token and leave HTTPS off
scripts/setup.sh --root ~/private-wiki --https off

# Create the venv and install base + dev dependencies (pytest, ruff)
scripts/setup.sh --with-dev --root ~/private-wiki --https off

# Rebuild the venv from scratch
scripts/setup.sh --recreate
```

The script:
- Detects an available Python 3.10+ interpreter.
- Creates `.venv/` if it does not exist.
- Installs packages from `requirements.txt` (and `requirements-dev.txt`
  with `--with-dev`).
- Verifies the import of the `wiki_core`, `mcp_server`, `rest_api`
  modules.
- Installs the `wiki-kiss` and `wiki-kiss-mcp` commands.
- Generates `.wiki-kiss.env` (mode `0600`) and prints the configured token.

## Available transports

The project exposes **three transports** that talk to the 5 MCP tools
(`list_pages`, `read_page`, `search`, `write_page`, `append_note`):

| Transport | Port | Use |
| --- | --- | --- |
| **stdio** | — | Local MCP clients (Claude Code, Claude Desktop, installed Open Cloud). The client launches the server as a subprocess. |
| **Streamable HTTP over HTTPS** | 8766 (default) | Remote MCP clients. TLS and a Bearer token are mandatory. |
| **REST/HTTP loopback** | 8765 (default) | Local HTTP clients; same Bearer token, no remote exposure. |

### Which to choose

- **stdio**: agents running on the same machine or through SSH/tunnel.
- **Streamable HTTP over HTTPS**: remote MCP-aware agents.
- **REST**: local clients that do not speak MCP.

## Starting and stopping services

### REST API (uvicorn)

```bash
# In background (default: 127.0.0.1:8765)
scripts/start-rest.sh

# Custom port; the host must stay on the loopback
scripts/start-rest.sh --host 127.0.0.1 --port 9000

# Foreground (Ctrl-C to stop)
scripts/start-rest.sh --foreground

# Auto-reload in development
scripts/start-rest.sh --reload
```

Main endpoints:
- `GET /health` — health check.
- `GET /stats` — wiki statistics.
- `GET /pages?subdir=...` — list pages.
- `GET /pages/{path:path}` — read.
- `PUT /pages/{path:path}` — write.
- `GET /search?q=...` — search.
- `POST /notes` — append note.
- `GET /docs` — interactive OpenAPI.

### MCP server (stdio)

The MCP server **does not** run as a daemon: it is started by the client
as a subprocess. For manual tests:

```bash
# Foreground start (Ctrl-C or EOF to exit)
scripts/start-mcp.sh
```

### MCP Streamable HTTPS server (for remote clients)

Configure and start with mandatory TLS and Bearer:

```bash
scripts/configure.sh --https on \
  --host 0.0.0.0 \
  --url https://wiki.example.com/mcp \
  --cert /path/fullchain.pem \
  --key /path/privkey.pem
```

Immediate shutdown, without interrupting CLI or MCP stdio:

```bash
scripts/configure.sh --https off
```

There is no remote MCP mode without authentication or without TLS.

### Recognised environment variables

| Variable             | Default        | Effect                              |
| -------------------- | -------------- | ----------------------------------- |
| `WIKI_ROOT`          | `./wiki`       | Wiki folder                         |
| `WIKI_LOG_LEVEL`     | `INFO`         | Python log level                    |
| `WIKI_MCP_TOKEN`     | (mandatory HTTP)| Unique MCP HTTPS/REST token        |
| `WIKI_HTTPS_ENABLED` | `0`            | Enables MCP HTTPS                   |
| `WIKI_HTTP_HOST`     | `127.0.0.1`    | MCP HTTPS host                      |
| `WIKI_HTTP_PORT`     | `8766`         | MCP HTTPS port                      |
| `WIKI_MCP_URL`       | (unset)        | Public URL `https://.../mcp`        |
| `WIKI_TLS_CERT`      | (unset)        | PEM certificate                     |
| `WIKI_TLS_KEY`       | (unset)        | PEM private key                     |
| `DEFAULT_HOST`       | `127.0.0.1`    | REST host (for `start-rest.sh`)     |
| `DEFAULT_PORT`       | `8765`         | REST port (for `start-rest.sh`)     |
| `NO_COLOR`           | (unset)        | Disable colours in the output       |

### Status and stop

```bash
# Current status (services, logs, pids)
scripts/status.sh

# Stop one or more services
scripts/stop.sh mcp
scripts/stop.sh mcp-http
scripts/stop.sh rest
scripts/stop.sh all
```

`var/run/*.pid` holds the pids, `var/log/*.log` the logs.

## Integration with MCP clients

### Local clients (stdio)

Generate the MCP configuration ready to paste:

```bash
scripts/install-mcp-client.sh --client claude-code
scripts/install-mcp-client.sh --client claude-desktop
scripts/install-mcp-client.sh --client generic

# Write to a file (e.g. .mcp.json for Claude Code)
scripts/install-mcp-client.sh --client claude-code --out .mcp.json
```

Typical output (for Claude Code / Claude Desktop):

```json
{
  "mcpServers": {
    "wiki-kiss": {
      "command": "/path/to/project/.venv/bin/python",
      "args": ["-m", "mcp_server", "--root", "/path/to/project/wiki"],
      "cwd": "/path/to/project",
      "env": {
        "WIKI_ROOT": "/path/to/project/wiki",
        "WIKI_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Where to put the snippet:

| Client         | Configuration file                                                |
| -------------- | ----------------------------------------------------------------- |
| Claude Code    | `.mcp.json` in the project root (or global `~/.claude.json`)      |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Open Cloud     | `mcpServers` section in the client settings                       |
| Perplexity     | MCP section of the client settings (when supported)               |

After saving the configuration **restart the client** so it reloads the
list of MCP servers.

### Remote clients (Streamable HTTP)

For Open Cloud updated or any other MCP-aware client that supports the
Streamable HTTP transport:

- URL: `https://wiki.example.com/mcp`
- Header: `Authorization: Bearer <token>`
- Header: `Accept: application/json, text/event-stream` (handled by the client)
- Protocol version: `2025-06-18`

## Agent onboarding

Generate a tailored skill with URL/path and protected credentials:

```bash
scripts/onboard-agent.sh --name customer-wiki --label "Customer Wiki"
```

The skill is created by default under `.agents/skills/generated/`, which is
git-ignored. After a token rotation regenerate it with `--force`. See
`ONBOARDING.md`.

## Tests and quality

```bash
# Run the pytest suite
scripts/run-tests.sh -q

# MCP stdio smoke test
.venv/bin/python tests/smoke_mcp.py

# Lint
.venv/bin/ruff check wiki_core mcp_server rest_api.py tests
```

## Troubleshooting

### The MCP client does not see the tool

1. Make sure the venv is active and `mcp_server` imports correctly:
   `scripts/status.sh` → verify the venv is detected.
2. Test manually: `scripts/start-mcp.sh < /dev/null` (it should start and
   stay waiting without errors).
3. Restart the MCP client after saving the configuration.
4. Check the venv path: it must be **absolute** in the MCP config.

### The REST port is busy

```bash
lsof -iTCP:8765 -sTCP:LISTEN
# Kill the process or pick a different port
scripts/start-rest.sh --port 9000
```

### `InvalidPathError` or `PageNotFoundError`

- The path contains `..` or unsupported characters: normalise it.
- The page does not exist: use `list_pages` or `search` to find it.

### MCP tests failing in `pytest`

```bash
.venv/bin/python -m pytest -q
```

If only the MCP tests fail, verify that `mcp` is installed in the venv:
`scripts/setup.sh --with-dev`.

## Common operations

- **Add a new stdio client**: `scripts/install-mcp-client.sh` and paste
  the config.
- **Add a new HTTP client (cloud)**: share URL and Bearer token. The
  client connects to `https://.../mcp` with
  `Authorization: Bearer <token>`.
- **Change the wiki root**: `scripts/configure.sh --root /new/root`.
- **Rotate the token**: `scripts/configure.sh --rotate-token`, then
  regenerate authorised skills with
  `scripts/onboard-agent.sh --force`.
- **Backup**: `tar czf wiki-$(date +%F).tgz wiki/` (everything is text).
- **Migration**: copy the `wiki/` folder to another machine and restart
  the services: no database to worry about.

## Operational philosophy (KISS)

- No database. No CMS. Version with Git.
- One optional local REST service. One MCP stdio server. One optional
  MCP HTTPS server.
- Content is readable even with `cat` or a Markdown editor.
- Important decisions go in `wiki/decisions/` as ADRs.
