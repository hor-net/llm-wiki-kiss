# Agents — llm-wiki-kiss

This document describes the **llm-wiki-kiss** ecosystem: a **KISS** (Keep It
Simple, Stupid) self-hosted wiki for AI agents. It is designed to offer a
persistent, portable, 100% user-controlled knowledge base, accessible to
different models through **MCP** (Model Context Protocol).

---

## Overview

**llm-wiki-kiss** turns static Markdown files into a shared source of truth
across AI agents. It solves the problem of knowledge fragmented across tools,
notebooks and conversations: everything is persistently archived on the
filesystem and uniformly exposed through a standardised MCP contract.

### Philosophy
- **KISS**: no database, no complex CMS, just files and links.
- **Persistent**: the wiki survives between agent sessions.
- **Portable**: a `tar.gz` of the folder is the whole backup.
- **Multicast**: the same content serves Claude Code, Open Cloud, Perplexity,
  Python scripts, etc.

---

## Architecture

```
llm-wiki-kiss/
├── wiki/                    # Markdown data (your wiki)
│   ├── index.md            # main entry point
│   ├── projects/           # project documentation
│   ├── notes/              # quick notes, ideas, observations
│   ├── decisions/          # ADRs and technical decisions
│   ├── references/         # external links and sources
│   ├── assets/             # images, attachments
│   └── logs/               # append-only logs (YYYY-MM-DD.md)
├── wiki_core/              # storage, validation, search, locking and CLI
├── mcp_server/             # MCP stdio + Streamable HTTP over TLS, single-wiki
├── rest_api.py             # FastAPI HTTP fallback
├── scripts/                # setup, configure, CLI and service management
├── tests/                  # pytest + MCP smoke tests
├── CONFIGURATION.md        # root, token, TLS and HTTPS toggle
├── ONBOARDING.md           # per-instance skills with private connection
├── .agents/skills/         # SKILL.md templates for AI agents
└── pyproject.toml          # project metadata, dependencies, tooling
```

### MCP tools (5 total)

| Tool | Description | Type |
|------|-------------|------|
| `list_pages` | Lists pages in the wiki (optional `subdir`). | Read |
| `read_page` | Reads the full content of a page. | Read |
| `search` | Case-insensitive full-text search with snippet and line number. | Read |
| `write_page` | Creates or overwrites a page and regenerates indexes. | Protected write |
| `append_note` | Appends text to a page or the daily log and regenerates indexes. | Protected write |

### Servers and ports

- **MCP stdio**: local process, for agents using IPC.
- **MCP Streamable HTTP over HTTPS** (optional): TLS and Bearer are mandatory.
- **REST API (FastAPI)**: optional fallback, protected by the same Bearer.

Defaults: `127.0.0.1:8765` (local REST), `127.0.0.1:8766` (MCP HTTPS).

### Offline local access

- MCP `stdio`: `python -m mcp_server --root /path/wiki`; it only talks over
  `stdin`/`stdout` and never opens sockets.
- CLI: `scripts/wiki.sh` or `python -m wiki_core.cli`; exposes `list`,
  `read`, `search`, `write`, `append`, `stats` and `rebuild-indexes`.
- MCP stdio and the CLI do not require `WIKI_MCP_TOKEN`; protection is
  delegated to the user and filesystem permissions.
- All mutations still go through `WikiStorage` and respect the lock.

### Isolation model

Each process or container serves exactly one `WIKI_ROOT` and uses a single
`WIKI_MCP_TOKEN` for both HTTP transports. Different customers or wikis must
run in separate containers, with independent filesystems, tokens and ports.
Do not introduce multi-tenant routing or wiki registries inside the process.

### Setup and configuration

- `scripts/setup.sh --root PATH --https off` installs the project, creates
  the root, generates the token and prints `WIKI_MCP_TOKEN=...`.
- `scripts/configure.sh` writes the configuration into `.wiki-kiss.env`
  with mode `0600`; the file is git-ignored and takes precedence over `.env`.
- HTTPS is off by default. `configure.sh --https on --cert CERT --key KEY`
  persists the configuration and starts the service; `configure.sh --https
  off` stops it and disables it.
- `start-mcp-http.sh` must refuse to start without the enable flag, the
  token, the certificate or the key. Do not add cleartext HTTP fallbacks.
- For wildcard binding (`0.0.0.0`/`::`) `WIKI_MCP_URL` is mandatory; the
  onboarding script uses it to configure clients.
- The REST API is allowed only on the loopback; remote access goes through
  MCP HTTPS.
- Token rotation: `configure.sh --rotate-token`; explicit read:
  `configure.sh --show-token`.
- Operational guide: [`CONFIGURATION.md`](CONFIGURATION.md).

### Agent onboarding

- `scripts/onboard-agent.sh` generates a personalised Agent Skills entry.
- Default output: `.agents/skills/generated/<name>/`, git-ignored.
- `references/connection.json` and `mcp-config.json` hold root, URL and
  token; directories and files must keep modes `0700` and `0600` respectively.
- `auto` mode picks HTTPS when enabled, otherwise MCP stdio local.
- Never print the token during onboarding and never commit generated skills.
- After `configure.sh --rotate-token`, regenerate authorised skills with
  `--force`; delete revoked ones.
- Full specification: [`ONBOARDING.md`](ONBOARDING.md).

### Concurrency and resilience

Concurrency stays filesystem-based, with no external services:

- reads, listings and searches do not take any lock and run in parallel;
- every mutation acquires an exclusive lock **per wiki root**;
- the lock combines a process-wide `RLock` and an OS file lock
  (`.wiki-kiss.lock`) to coordinate across processes;
- pages and indexes are written to temporary files in the same directory,
  flushed and published via `os.replace`, so a reader never sees a partial
  file;
- `append_note` is a protected read-modify-write: concurrent appends are
  never lost;
- index regeneration happens inside the same critical section as the
  mutation;
- the default timeout is 10 seconds and raises `WriteLockTimeoutError`.

The lock only coordinates processes that use `WikiStorage`. Editors or
scripts that write directly to the files can bypass it; with multiple agents,
all mutations must therefore go through the core, MCP or the REST API. The
lock file is a technical artifact: do not delete it while running and it
cannot remain "stuck" after a process dies, because the lock is managed by
the operating system.

---

## Storage and contents

### Format
- Plain **Markdown**, UTF-8. (HTML supported as well for rich content.)
- Relative internal links: `[text](../notes/idea.md)`, `[# Section](#title)`.
- `kebab-case` filenames.
- No mandatory frontmatter; the first heading is the page name.

### Conventions
1. Every page starts with `# Title`.
2. Relative links to parent folders: `[other](../notes/idea.md)`.
3. **No database**: simple backup with `tar`, immediate migration.
4. Versioned with Git; every commit is a stable checkpoint.

### Page types (best practice)

| Category        | Purpose                                         | Folder        |
|------------------|-------------------------------------------------|----------------|
| `projects/*.md`  | Project docs, roadmaps, specifications          | `projects/`   |
| `notes/*.md`     | Quick notes, ideas, observations                | `notes/`      |
| `decisions/*.md` | ADRs (Architecture Decision Records)            | `decisions/`  |
| `references/*`   | External links, sources, articles               | `references/` |
| `assets/*`       | Images, PDFs, audio                             | `assets/`     |
| `logs/*.md`      | Append-only operational logs                    | `logs/`       |

---

## REST API

A minimal API acts as a fallback for legacy clients. It exposes the same base
operators as the MCP tools, plus `/health` and `/stats`. Main endpoints:

- `GET /health` — health check
- `GET /stats` — wiki statistics (page count, total size)
- `GET /pages?subdir=…` — list pages in the root or in a subdir
- `GET /pages/{path:path}` — read a page
- `PUT /pages/{path:path}` — create/overwrite a page, returns metadata
- `GET /search?q=…` — full-text search with snippet and line number
- `POST /notes` — append note (defaults to the daily log)

`/health` is public but does not expose the root or content. All other
endpoints, including `/docs` and `/openapi.json`, require
`Authorization: Bearer <WIKI_MCP_TOKEN>`. Without a token the service
replies `503` and does not serve data.

---

## Client configuration

Configure an MCP server in your AI client. Example: Claude Code, Open
Cloud, Perplexity.

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

Main variables: `WIKI_ROOT`, `WIKI_MCP_TOKEN`, `WIKI_HTTPS_ENABLED`,
`WIKI_HTTP_HOST`, `WIKI_HTTP_PORT`, `WIKI_MCP_URL`, `WIKI_TLS_CERT`,
`WIKI_TLS_KEY`, `WIKI_LOG_LEVEL`, `NO_COLOR`.

### Management scripts (`scripts/*`)

| Script                          | Purpose                                                      |
|---------------------------------|--------------------------------------------------------------|
| [`setup.sh`](scripts/setup.sh)  | Installs and configures root, token and HTTPS state.         |
| `configure.sh`                  | Updates root/token and toggles MCP HTTPS.                    |
| `onboard-agent.sh`              | Generates a private skill with URL/path and credentials.     |
| `start-mcp.sh`                  | Launches the MCP stdio server (local, no network).            |
| `wiki.sh`                       | Local CLI for content and index maintenance.                 |
| `start-mcp-http.sh`             | Launches MCP HTTPS only when enabled.                        |
| `start-rest.sh`                 | Starts the REST API in background.                           |
| `stop.sh {mcp|mcp-http|rest}`   | Stops services.                                              |
| `status.sh`                     | Shows status, pids, logs.                                    |
| `run-tests.sh`                  | Wrapper around pytest, accepts pytest arguments.             |

---

## AI agent skills

In `.agents/skills/` two ready `SKILL.md` files:

1. **wiki-kiss-bridge**: tools to read, search and append information to the
   wiki (for agents that want to use the knowledge base).
2. **wiki-kiss-operator**: install, start, operate and troubleshoot.

Copy them into `~/.claude/skills/` (or the path expected by your client) and
restart the agent to load the skills.

---

## Tests and quality

```bash
scripts/run-tests.sh -q
.venv/bin/python -m pytest -q
.venv/bin/ruff check wiki_core mcp_server rest_api.py tests
```

- **pytest** for storage, CLI, authentication and thread/process concurrency.
- **Smoke tests** for MCP stdio and the TLS-protected HTTP transport.
- **Ruff** for linting/style.

### Core change rules

1. Do not introduce databases, Redis or external queues without a proven
   requirement.
2. Keep a single root and a single token per process; use separate
   containers, non-shared volumes and distinct tokens for different customers.
3. Never write pages or indexes directly from the handlers: use `WikiStorage`.
4. Every new mutation must use the root write lock and atomic writes.
5. Reads must stay lock-free; they accept seeing the complete previous or
   next version, never a partial file.
6. Indexes are derived and deterministic data: no LLM in their generation.
7. Add concurrency tests when the write path changes.

---

## Markdown page example

```markdown
# HoRNetMBC

**HoRNet** · version 1.0.4 · Dynamics

## Repository

- **GitHub:** https://github.com/hor-net/HoRNetMBC
- **Local path:** `/Users/.../Projects/HoRNetMBC`

## Plugin identifiers

- **Manufacturer ID:** `HrNt`
- **Unique ID:** `bI8H`
- **AAX Type IDs:** `IEF1, IEF2`

## Build

- Cross-platform build script in `scripts/`
- Installer under `installer/` for macOS/Windows
```

---

## Security

- Path validation: no arbitrary symlinks or `..`.
- 2 MiB per-page limit.
- Scope limited to the wiki root (`WIKI_ROOT`).
- TLS and Bearer authentication mandatory for remote MCP; Bearer mandatory
  for local REST; fail-closed if `WIKI_MCP_TOKEN` is not configured.
- Public health checks do not expose root, paths or content.
- All HTTP responses use `Cache-Control: no-store` and must not be cached by
  browsers or proxies.

---

## License, contributions and references

- **License:** GNU AGPL v3 or later — Copyright (C) 2026 Hornet SRL.
- **Contributing:** issues and PRs are welcome; guidelines in README.md.
- **MCP reference:** https://modelcontextprotocol.io
- **Unix philosophy:** "do one thing and do it well".
