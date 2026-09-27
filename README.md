# llm-wiki-kiss

[![License: AGPL v3 or later](https://img.shields.io/badge/License-AGPLv3%2B-blue.svg)](./LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-8A2BE2)](https://modelcontextprotocol.io)
[![Tests](https://github.com/hor-net/llm-wiki-kiss/actions/workflows/tests.yml/badge.svg)](https://github.com/hor-net/llm-wiki-kiss/actions/workflows/tests.yml)
[![Made with KISS](https://img.shields.io/badge/principle-KISS-ff69b4)](#philosophy)

> **A KISS self-hosted wiki for AI agents** — Markdown files on the
> filesystem, uniform access via **MCP** (stdio) and an optional **REST/HTTPS**
> fallback. Same content, no matter which agent: Claude Code, Open Cloud,
> Perplexity, Python scripts, browser.

---

## Contents

- [TL;DR](#tldr)
- [Why this exists](#why-this-exists)
- [Features](#features)
- [Quick start (5 minutes)](#quick-start-5-minutes)
- [Architecture](#architecture)
- [Manual installation](#manual-installation)
- [Configuration](#configuration)
- [Offline local usage](#offline-local-usage)
- [The 5 MCP tools](#the-5-mcp-tools)
- [REST API](#rest-api)
- [MCP Streamable HTTPS (cloud clients)](#mcp-streamable-https-cloud-clients)
- [MCP client configuration](#mcp-client-configuration)
- [Skills for agents](#skills-for-agents)
- [Custom onboarding](#custom-onboarding)
- [Management scripts](#management-scripts)
- [Tests and quality](#tests-and-quality)
- [Wiki layout](#wiki-layout)
- [Philosophy](#philosophy)
- [Advantages and limits](#advantages-and-limits)
- [Contributing](#contributing)
- [License](#license)
- [Credits](#credits)

---

## TL;DR

Imagine you have a bunch of notes about your work scattered across random
chat windows, sticky notes on your desk and half-finished documents on your
laptop. Now imagine one of those smart AI assistants (the "LLM" thing)
that everybody keeps talking about) could read all of those notes, learn
from them, add new ones, and never forget anything you told it. Cool, right?

That's exactly what this project does.

The idea is stupidly simple: take a normal folder full of normal `.md`
files (the same kind of files you already write everywhere), and let any AI
assistant read and write them through a standard protocol called
**Model Context Protocol** (MCP). No magic, no database, no complicated
setup. Just plain text files that you and the AI can both understand.

Three flavours of access, pick the one you want:

1. **MCP stdio** — the AI assistant launches this tiny program on your
   computer, talks to it through standard input/output (the kind of thing
   every program already does). No internet needed, super fast, super safe.
   This is the default and it works offline.
2. **CLI** — a normal command-line tool (`wiki-kiss`) that you can run
   from your terminal. Great for scripts, cron jobs, and shell power users.
3. **MCP Streamable HTTPS** — if you want the AI to connect over the
   network (maybe from another machine or a cloud service), turn on TLS +
   Bearer token authentication. Off by default, enabled with one command.

That's it. No database to install, no Docker to learn, no cloud account
to create. If you know how to clone a Git repo and run a shell script,
you've already understood 90% of the project.

If you want the long, detailed version of how to actually use it, keep
reading. The whole README is basically a friendly walkthrough of every
command, every setting, and every file, with copy-pasteable examples. Have
fun.

---

## Why this exists

Knowledge shared between AI agents today lives scattered across tools,
notebooks and conversations that disappear the moment you close the tab.
This project provides a **persistent, portable, 100% user-controlled
knowledge base**:

- 📁 `.md` or `.html` files readable with any editor
- 🧠 A standardized **MCP server** any agent can use
- 🌐 A minimal **REST API** as a fallback for clients that do not support MCP
- 🪶 No database, no CMS, versioned with Git
- 🔌 Works anywhere: local, private server, container, codespace
- 🔒 One process per wiki, one token per process, file lock between
  threads and processes
- 🧰 CLI + REST + stdio MCP + Streamable HTTPS MCP, all in a few
  hundred lines of Python
- 🧑‍💻 A configurable Agent Skill generator so a single LLM client
  gets a tailored skill per instance

The goal is to be a small, portable, auditable replacement for any
closed-source "AI memory" service.

---

## Features

- **Filesystem storage**: one folder with Markdown files and relative
  links. No SQL, no MongoDB, no Redis. `tar` the folder and you have a
  full backup.
- **KISS concurrency**: reads are lock-free; writes are serialised per
  root through a thread `RLock` paired with an OS file lock, so two
  processes writing the same wiki never corrupt it. Pages and indexes
  are published atomically with `tempfile + fsync + os.replace`, so a
  reader never sees a partial file.
- **MCP stdio server** with five tools: `list_pages`, `read_page`,
  `search`, `write_page`, `append_note`. Same JSON schema for all
  transports.
- **MCP Streamable HTTPS server** (MCP 2025-06-18) for remote clients.
  TLS and Bearer token are mandatory; if the token is not configured the
  server stays **fail-closed** and replies `503`.
- **FastAPI REST API** protected by the same Bearer token, with OpenAPI
  docs on `/docs`. REST accepts loopback binding only.
- **Local CLI** (`wiki-kiss` / `scripts/wiki.sh`) for offline content
  access. Reads return raw Markdown, mutations return JSON.
- **Per-instance Agent Skills**: `scripts/onboard-agent.sh` generates a
  tailored `SKILL.md` plus a protected `connection.json` and an MCP
  client config ready for Claude Code, Claude Desktop, Pi or any
  Agent Skills compatible client.
- **Configuration persistence**: root, token, host, port, TLS
  certificate and key are stored in `.wiki-kiss.env` with mode `0600`.
  `scripts/configure.sh` rotates the token, toggles HTTPS, restarts the
  services and writes the file atomically.
- **Path safety**: pages can never escape the wiki root, no `..`,
  no NUL bytes, max 2 MiB per page, OS-enforced locking.
- **Privacy by default**: public health checks never expose root, paths
  or content; HTTP responses set `Cache-Control: no-store`,
  `X-Content-Type: nosniff`, `Referrer-Policy: no-referrer`.
- **Scripted operational tools**: setup, configure, onboard, start, stop,
  status, run-tests, onboard-agent. All shell scripts pass
  `bash -n` and live in `scripts/`.
- **Continuous integration**: GitHub Actions matrix on Python
  3.10–3.13 with `pytest`, `ruff`, Bash validation, MCP stdio and
  Streamable HTTPS smoke tests, plus Gitleaks and Dependabot.

---

## Quick start (5 minutes)

Requirement: **Python 3.10+**.

```bash
# 1. Clone and configure
git clone https://github.com/hor-net/llm-wiki-kiss.git
cd llm-wiki-kiss

# 2. Install, pick the root, generate the token and leave HTTPS off
scripts/setup.sh --with-dev --root ./wiki --https off

# 3. Read the generated token and start the local REST API
export WIKI_MCP_TOKEN="$(scripts/configure.sh --show-token)"
scripts/start-rest.sh

# 4. Verify (health is public, data is authenticated)
scripts/status.sh
curl http://127.0.0.1:8765/health
curl -H "Authorization: Bearer $WIKI_MCP_TOKEN" http://127.0.0.1:8765/stats
```

To integrate with Claude Code / Claude Desktop / Open Cloud / Perplexity:

```bash
scripts/onboard-agent.sh --name customer-wiki --label "Customer Wiki"
```

Copy the output into your client configuration file and restart it.

---

## Architecture

```
llm-wiki-kiss/
├── wiki/                  # Markdown data (your wiki)
│   ├── index.md
│   ├── projects/  notes/  decisions/  references/  assets/  logs/
├── wiki_core/             # filesystem logic (WikiStorage, validation, search)
├── mcp_server/            # MCP stdio + Streamable HTTPS server (5 tools)
├── rest_api.py            # FastAPI HTTP fallback
├── scripts/               # setup, configure, CLI, start, stop, status
├── tests/                 # pytest + MCP smoke tests via stdio and HTTPS
├── .agents/skills/        # template SKILL.md for AI agents
├── CONFIGURATION.md       # root, token, TLS and HTTPS toggle
├── ONBOARDING.md          # per-instance skill generation
├── SECURITY.md            # threat model and reporting
├── CONTRIBUTING.md        # contributor guide
├── CHANGELOG.md           # release history
├── pyproject.toml, requirements*.txt, .env.example, .gitignore
├── LICENSE                # GNU AGPL v3 or later
└── README.md
```

**Request flow** for the most common case (local agent, stdio):

```text
+-----------------+        stdio JSON-RPC        +-------------------+
|  LLM client     |  <----------------------->  |  mcp_server.py    |
|  (Claude Code,  |                             |  (WikiStorage)    |
|   Pi, …)        |                             +---------+---------+
+-----------------+                                       |
                                                          v
                                              +-----------+-----------+
                                              |  wiki/ Markdown files  |
                                              |  .wiki-kiss.lock (OS)   |
                                              +-----------------------+
```

**Request flow** for remote MCP:

```text
+-----------------+        HTTPS + Bearer        +-------------------+
|  Cloud client   |  <----------------------->  |  mcp_server.http   |
|  (Open Cloud)   |                             |  (BearerAuthMW)    |
+-----------------+                             +---------+---------+
                                                          |
                                                          v
                                              +-----------+-----------+
                                              |  WikiStorage + TLS    |
                                              +-----------------------+
```

---

## Manual installation

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # + requirements-dev.txt for development
```

`scripts/setup.sh` automates the same flow and can also generate the
token and HTTPS configuration in one step.

---

## Configuration

[`scripts/configure.sh`](scripts/configure.sh) selects the root, generates or
rotates the token and actually turns the MCP HTTPS interface on or off.
Settings are persisted in `.wiki-kiss.env` with mode `0600`.

```bash
scripts/configure.sh                              # interactive mode
scripts/configure.sh --root ~/private-wiki --https off
scripts/configure.sh --show-token
scripts/configure.sh --rotate-token
scripts/configure.sh --https off                  # stops and disables HTTPS
scripts/configure.sh --https on                   # reuses the saved cert and key
```

HTTPS always requires a PEM certificate and key. The full guide, including a
self-signed certificate for local tests, lives in
[`CONFIGURATION.md`](CONFIGURATION.md).

### Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `WIKI_ROOT` | `./wiki` | Folder containing the Markdown files |
| `WIKI_MCP_TOKEN` | (auto) | Bearer token required for HTTP transports |
| `WIKI_HTTPS_ENABLED` | `0` | Turns MCP HTTPS on/off |
| `WIKI_HTTP_HOST` | `127.0.0.1` | Host for MCP HTTPS |
| `WIKI_HTTP_PORT` | `8766` | Port for MCP HTTPS |
| `WIKI_MCP_URL` | (unset) | Public URL `https://.../mcp` (required with `0.0.0.0`) |
| `WIKI_TLS_CERT` | (unset) | PEM certificate for HTTPS |
| `WIKI_TLS_KEY` | (unset) | PEM private key for HTTPS |
| `WIKI_LOG_LEVEL` | `INFO` | Python log level |
| `DEFAULT_HOST` | `127.0.0.1` | REST host |
| `DEFAULT_PORT` | `8765` | REST port |
| `NO_COLOR` | (unset) | Disable colour output |

---

## Offline local usage

Neither MCP `stdio` nor the CLI open ports or require a token. Both access the
single `WIKI_ROOT` directly and reuse `WikiStorage` for locking, validation
and atomic writes.

### MCP stdio

The client configuration shown later runs:

```bash
.venv/bin/python -m mcp_server --root /path/to/wiki
```

Communication happens over the local subprocess `stdin`/`stdout`: no HTTP, DNS
or network connection involved.

### CLI

From the checkout use `scripts/wiki.sh`; after installing the package the
`wiki-kiss` console script is also available.

```bash
scripts/wiki.sh list
scripts/wiki.sh read notes/idea.md
scripts/wiki.sh search "text to find" --subdir notes
scripts/wiki.sh write notes/idea.md --content $'# Idea\n\nContent'
printf '# From stdin\n\nText\n' | scripts/wiki.sh write notes/stdin.md
scripts/wiki.sh append logs/manual.md --content "Operation completed"
printf 'Note from a local process\n' | scripts/wiki.sh append
scripts/wiki.sh stats
scripts/wiki.sh rebuild-indexes
```

The root can be picked with `--root /path/wiki` or via `WIKI_ROOT`. `read`
outputs raw Markdown; `list`, `search`, `write`, `append` and `stats` emit
JSON, so they can be reused by scripts and local agents. Local access follows
filesystem permissions: for a private wiki use an unshared root and, on Unix,
restrictive permissions such as `chmod -R go-rwx /path/wiki`.

---

## The 5 MCP tools

| Tool          | Purpose                                                       |
| ------------- | ------------------------------------------------------------- |
| `list_pages`  | Lists pages, optional `subdir`.                               |
| `read_page`   | Reads the content of a page by path.                          |
| `search`      | Case-insensitive full-text search with snippet and line.      |
| `write_page`  | Creates or overwrites a page; appends `.md` when missing.     |
| `append_note` | Appends text. Defaults to the daily log `logs/YYYY-MM-DD.md`. |

All paths are **relative** to the wiki root and separated by `/`.

### Concurrency

Reads are lock-free. `write_page`, `append_note` and index regeneration are
serialised per root through `.wiki-kiss.lock`, valid across threads and
processes. Writes use temporary files, `fsync` and `os.replace`: a reader
never sees a partial file, only the previous or next complete version.
Distinct instances or containers remain independent. The MCP handlers run the
filesystem operations in the standard thread pool so they never block the
event loop.

Coordination only applies to mutations that go through `WikiStorage`. Scripts
and editors that write directly to the root bypass the lock.

### Quick examples

```json
// list_pages
{ "subdir": "notes" }

// read_page
{ "path": "notes/example-note.md" }

// search
{ "query": "MCP", "max_results": 20 }

// write_page
{ "path": "notes/idea.md", "content": "# Idea\n\n...", "overwrite": false }

// append_note (path optional: defaults to today's log)
{ "content": "Refactor started.", "heading": "Refactor" }
```

---

## REST API

| Method | Endpoint                     | Description                              |
| ------ | ---------------------------- | ---------------------------------------- |
| GET    | `/health`                    | Health check                             |
| GET    | `/stats`                     | Wiki statistics                          |
| GET    | `/pages?subdir=...`          | List pages                               |
| GET    | `/pages/{path:path}`         | Read a page                              |
| PUT    | `/pages/{path:path}`         | Write a page                             |
| GET    | `/search?q=...`              | Full-text search                         |
| POST   | `/notes`                     | Append note (defaults to daily log)      |
| GET    | `/docs`                      | Interactive OpenAPI (Swagger UI)         |

All REST endpoints, including `/docs` and `/openapi.json`, require
`Authorization: Bearer <WIKI_MCP_TOKEN>`. Only `/health` is public and it does
not expose root, paths or content. HTTP responses set
`Cache-Control: no-store`. Without a token the service stays **fail-closed**
and replies `503` without serving data.

---

## MCP Streamable HTTPS (cloud clients)

The MCP server is also exposed via HTTPS with the **Streamable HTTP** transport
(MCP 2025-06-18), so MCP-aware cloud clients (Open Cloud updated, etc.) can
connect without launching a subprocess.

```bash
scripts/configure.sh --https on \
  --host 0.0.0.0 \
  --port 8766 \
  --url https://wiki.example.com/mcp \
  --cert /path/to/fullchain.pem \
  --key /path/to/privkey.pem
```

The client connects to `https://HOST:8766/mcp` with:

```
POST /mcp
Authorization: Bearer long-random-secret
Accept: application/json, text/event-stream
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"method":"tools/list"}
```

Turn it off at any time with `scripts/configure.sh --https off`. MCP stdio and
the CLI keep working. For a public service use a trusted certificate (for
example Let's Encrypt) or terminate TLS in a reverse proxy.

The process serves a single root (`WIKI_ROOT`) with a single mandatory token
(`WIKI_MCP_TOKEN`). Without a token both HTTP transports stay fail-closed. To
serve different customers or wikis, run separate instances or containers
with independent filesystems, tokens and ports. Never share volumes or tokens
across customers.

---

## MCP client configuration

Example snippet for Claude Code / Claude Desktop / Open Cloud / Perplexity
(generated by `scripts/onboard-agent.sh`):

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

| Client         | Configuration file                                                |
| -------------- | ----------------------------------------------------------------- |
| Claude Code    | `.mcp.json` in the project root (or global `~/.claude.json`)      |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Open Cloud     | `mcpServers` section in the client settings                       |
| Perplexity     | MCP section of the client settings (when supported)               |

After saving the configuration **restart the client** so it reloads the list
of MCP servers.

---

## Skills for agents

In [`.agents/skills/`](./.agents/skills/) you find two ready `SKILL.md` files
loadable by TRAE, Claude Code and other compatible agents:

| Skill                  | When the agent uses it                                          |
| ---------------------- | --------------------------------------------------------------- |
| `wiki-kiss-bridge`     | Reading, searching, writing, citing wiki content.               |
| `wiki-kiss-operator`   | Installing, starting, stopping, integrating or troubleshooting.  |

Copy the folders into `~/.claude/skills/` (or the path expected by your
client) to use them locally. Pi automatically discovers project skills under
`.agents/skills/`.

---

## Custom onboarding

Generate a personalised Agent Skill for the configured instance:

```bash
scripts/onboard-agent.sh --name customer-wiki --label "Customer Wiki"
```

`auto` mode uses HTTPS when it is enabled and configured, otherwise MCP stdio
over the filesystem. The skill contains:

- a tailored `SKILL.md`;
- `references/connection.json` with root, URL and token;
- `references/mcp-config.json` ready to be adapted to the client.

The default destination `.agents/skills/generated/` is git-ignored. Files
have mode `0600` and contain real credentials: do not share or commit them.
After a token rotation regenerate the skill with `--force`. See
[`ONBOARDING.md`](ONBOARDING.md) for local/remote modes, global install and
revocation.

---

## Management scripts

All scripts accept `--help`. Logs go to `var/log/`, pids to `var/run/`.

| Script                              | Purpose                                                |
| ----------------------------------- | ------------------------------------------------------ |
| `scripts/setup.sh`                  | Creates or updates the venv and installs dependencies.  |
| `scripts/setup.sh --with-dev`       | + pytest, ruff, httpx.                                 |
| `scripts/setup.sh --recreate`       | Rebuilds the venv from scratch.                        |
| `scripts/configure.sh`              | Configures root, token and MCP HTTPS state.            |
| `scripts/onboard-agent.sh`          | Generates a private skill with URL/path and credentials. |
| `scripts/start-mcp.sh`              | Starts the MCP stdio server (local, no network).       |
| `scripts/wiki.sh`                   | Local CLI to read, search and edit the wiki.           |
| `scripts/start-mcp-http.sh`         | Starts MCP HTTPS only when enabled and configured.     |
| `scripts/start-rest.sh`             | Starts the REST API in background.                     |
| `scripts/start-rest.sh --foreground` | Starts the REST API in foreground.                     |
| `scripts/start-rest.sh --reload`    | Development mode with auto-reload.                     |
| `scripts/stop.sh {mcp\|mcp-http\|rest\|all}` | Stops one or more services.                 |
| `scripts/status.sh`                 | Shows status, pids and logs.                           |
| `scripts/onboard-agent.sh`          | Generates a private skill with URL/path and credentials. |
| `scripts/run-tests.sh`              | Wrapper around `pytest` (accepts pytest arguments).     |

Main variables: `WIKI_ROOT`, `WIKI_MCP_TOKEN`, `WIKI_HTTPS_ENABLED`,
`WIKI_HTTP_HOST`, `WIKI_HTTP_PORT`, `WIKI_MCP_URL`, `WIKI_TLS_CERT`,
`WIKI_TLS_KEY`, `WIKI_LOG_LEVEL`, `DEFAULT_HOST`, `DEFAULT_PORT`, `NO_COLOR`.
`configure.sh` manages `.wiki-kiss.env`, which takes precedence over any
`.env`.

---

## Tests and quality

```bash
scripts/run-tests.sh -q
.venv/bin/python -m pytest -q
.venv/bin/python tests/smoke_mcp.py       # MCP stdio smoke test
.venv/bin/python tests/smoke_mcp_http.py  # MCP Streamable HTTPS smoke test
.venv/bin/ruff check wiki_core mcp_server rest_api.py tests
```

The GitHub Actions matrix runs `pytest` on Python 3.10, 3.11, 3.12 and
3.13, plus `ruff`, Bash validation and the two smoke tests.

---

## Wiki layout

Example organisation of the `wiki/` folder:

```
wiki/
├── index.md
├── projects/         # project documentation
├── notes/            # quick notes, ideas, observations
├── decisions/        # ADRs (NNNN-title.md)
├── references/       # external links and sources
├── assets/           # images, attachments
└── logs/             # append-only logs (YYYY-MM-DD.md)
```

**Conventions**:

- Plain Markdown files, UTF-8.
- `kebab-case` filenames.
- Each page starts with a level-1 title (`# Title`).
- Internal links are relative: `[another page](../notes/idea.md)`.
- No mandatory frontmatter: add it only when real metadata is needed.

---

## Philosophy

KISS first.

- **The wiki holds stable knowledge**: decisions, projects, references.
- **Conversational memory is handled elsewhere** (e.g. QMD): it covers
  short-lived, dynamic context, not long-term knowledge.
- **MCP makes that knowledge available to any agent**: one contract,
  infinite integrations.
- **No database**: `tar czf wiki-$(date +%F).tgz wiki/` is the backup.
- **No lock-in**: everything is text, everything is versionable with Git.

---

## Advantages and limits

**Advantages**: full control, trivial backup, immediate migration, easy
debugging, compatibility with multiple AI agents, gradual growth, auditable
codebase, no cloud lock-in.

**Limits**: no automatic backlinks, no native database, no rich UI, no
distributed transactions. Quality depends on discipline in writing and
naming conventions. The file lock relies on a filesystem that supports
operating-system locks correctly. Multi-tenant hosting must be done by
running multiple processes or containers, not by adding routing inside the
process.

---

## Contributing

Issues and PRs are welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before
proposing changes. For vulnerabilities use the private procedure described
in [`SECURITY.md`](SECURITY.md), never a public issue.

- Code follows Ruff; tests are mandatory for core changes.
- Wiki style: ADRs in `decisions/`; reference:
  [`wiki/decisions/0001-storage-filesystem.md`](wiki/decisions/0001-storage-filesystem.md).
- Release history: [`CHANGELOG.md`](CHANGELOG.md).
- Release process: [`RELEASING.md`](RELEASING.md).

---

## License

[GNU AGPL v3 or later](./LICENSE) — Copyright (C) 2026 Hornet SRL.

You can use and sell the service as long as you respect the licence terms. In
particular, the AGPLv3 requires you to offer the source of the modified
version to the users that run it as a network service. User data and wikis
do not become part of the licensed source code.

---

## Credits

Project inspired by the Model Context Protocol paper
(<https://modelcontextprotocol.io>) and the Unix philosophy "do one thing
and do it well".
