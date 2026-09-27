#!/usr/bin/env bash
# Generate a personalised Agent Skill for a single wiki-kiss instance.
set -euo pipefail

_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${_LIB}/lib.sh"

usage() {
  cat <<EOF
${C_BOLD}Uso:${C_RESET} scripts/onboard-agent.sh [opzioni]

Generate an Agent Skills skill with the local root, MCP HTTPS URL and
token from the current configuration. Sensitive files are created with
mode 600.

Options:
  --name NAME       Skill name (lowercase, digits and hyphens)
  --label TEXT      Human-readable wiki name
  --mode MODE       auto, local or https (default: auto)
  --target DIR      Skills directory (default: .agents/skills/generated)
  --force           Overwrite an existing skill with the same name
  -h, --help        Show this message

Examples:
  scripts/onboard-agent.sh --name private-wiki
  scripts/onboard-agent.sh --name private-wiki --mode local
  scripts/onboard-agent.sh --name remote-wiki --mode https --target ~/.agents/skills
EOF
}

NAME=""
LABEL=""
MODE="auto"
TARGET="${PROJECT_ROOT}/.agents/skills/generated"
FORCE=0
ARGUMENT_COUNT=$#

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)   NAME="$2"; shift 2 ;;
    --label)  LABEL="$2"; shift 2 ;;
    --mode)   MODE="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --force)  FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) log_error "Unknown argument: $1"; usage; exit 2 ;;
  esac
done

if [[ -n "${WIKI_CONFIG_FILE:-}" && -f "${WIKI_CONFIG_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${WIKI_CONFIG_FILE}"
  set +a
else
  load_env_file
fi

if [[ -z "${WIKI_ROOT:-}" || ! -d "${WIKI_ROOT}" ]]; then
  log_error "WIKI_ROOT not configured or missing. Run scripts/configure.sh."
  exit 2
fi
if [[ -z "${WIKI_MCP_TOKEN:-}" ]]; then
  log_error "Token not configured. Run scripts/configure.sh --rotate-token."
  exit 2
fi

root_name="$(basename "${WIKI_ROOT}")"
default_name="$(printf 'wiki-%s' "${root_name}" \
  | tr '[:upper:]' '[:lower:]' \
  | tr -cs 'a-z0-9-' '-' \
  | sed -E 's/^-+//; s/-+$//; s/-+/-/g')"
[[ -n "${default_name}" ]] || default_name="wiki-kiss-local"
NAME="${NAME:-${default_name}}"
LABEL="${LABEL:-${root_name}}"

if [[ "${ARGUMENT_COUNT}" -eq 0 && -t 0 ]]; then
  printf 'Skill name [%s]: ' "${NAME}"
  read -r answer
  NAME="${answer:-${NAME}}"
  printf 'Human-readable wiki name [%s]: ' "${LABEL}"
  read -r answer
  LABEL="${answer:-${LABEL}}"
  printf 'Mode auto/local/https [%s]: ' "${MODE}"
  read -r answer
  MODE="${answer:-${MODE}}"
fi

if [[ ! "${NAME}" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ || ${#NAME} -gt 64 ]]; then
  log_error "Invalid skill name: use lowercase, digits and hyphens (max 64)."
  exit 2
fi
if [[ "${LABEL}" == *$'\n'* || "${LABEL}" == *$'\r'* || -z "${LABEL}" ]]; then
  log_error "Invalid label."
  exit 2
fi

case "${MODE}" in
  auto)
    if [[ "${WIKI_HTTPS_ENABLED:-0}" == "1" && -n "${WIKI_MCP_URL:-}" ]]; then
      MODE="https"
    else
      MODE="local"
    fi
    ;;
  local|https) ;;
  *) log_error "Invalid mode: use auto, local or https."; exit 2 ;;
esac

if [[ "${MODE}" == "https" ]]; then
  if [[ "${WIKI_HTTPS_ENABLED:-0}" != "1" ]]; then
    log_error "HTTPS is not enabled. Use scripts/configure.sh --https on."
    exit 2
  fi
  if [[ -z "${WIKI_MCP_URL:-}" ]]; then
    log_error "WIKI_MCP_URL missing. Reconfigure HTTPS with --url."
    exit 2
  fi
  if [[ ! "${WIKI_MCP_URL}" =~ ^https://[^[:space:]]+/mcp/?$ ]]; then
    log_error "Invalid WIKI_MCP_URL: ${WIKI_MCP_URL}"
    exit 2
  fi
fi

TARGET="${TARGET/#\~/${HOME}}"
mkdir -p -m 700 "${TARGET}"
TARGET="$(cd "${TARGET}" && pwd -P)"
DESTINATION="${TARGET}/${NAME}"

if [[ -e "${DESTINATION}" && "${FORCE}" -ne 1 ]]; then
  log_error "The skill already exists: ${DESTINATION} (use --force to replace)."
  exit 1
fi
if [[ -e "${DESTINATION}" && ! -d "${DESTINATION}" ]]; then
  log_error "The path exists and is not a directory: ${DESTINATION}"
  exit 1
fi

umask 077
TEMPORARY="$(mktemp -d "${TARGET}/.${NAME}.tmp.XXXXXX")"
cleanup() { rm -rf "${TEMPORARY}"; }
trap cleanup EXIT
mkdir -m 700 "${TEMPORARY}/references"

export ONBOARD_NAME="${NAME}"
export ONBOARD_LABEL="${LABEL}"
export ONBOARD_MODE="${MODE}"
export ONBOARD_ROOT="$(cd "${WIKI_ROOT}" && pwd -P)"
export ONBOARD_URL="${WIKI_MCP_URL:-}"
export ONBOARD_TOKEN="${WIKI_MCP_TOKEN}"
export ONBOARD_PROJECT_ROOT="${PROJECT_ROOT}"
export ONBOARD_PYTHON="${VENV_PYTHON}"

"${PYTHON_BIN}" - "${TEMPORARY}" <<'PY'
from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

output = Path(sys.argv[1])
name = os.environ["ONBOARD_NAME"]
label = os.environ["ONBOARD_LABEL"]
mode = os.environ["ONBOARD_MODE"]
root = os.environ["ONBOARD_ROOT"]
url = os.environ["ONBOARD_URL"]
token = os.environ["ONBOARD_TOKEN"]
project_root = os.environ["ONBOARD_PROJECT_ROOT"]
python = os.environ["ONBOARD_PYTHON"]

description = (
    f"Access the private {label} wiki to search, read, write, and append persistent "
    "knowledge. Use whenever the user asks about this wiki or asks to remember, "
    "retrieve, document, or update information in its knowledge base."
)

connection = {
    "name": name,
    "label": label,
    "mode": mode,
    "wiki_root": root,
    "mcp_url": url or None,
    "bearer_token": token,
    "project_root": project_root,
    "python": python,
}
(output / "references" / "connection.json").write_text(
    json.dumps(connection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

if mode == "local":
    server = {
        "command": python,
        "args": ["-m", "mcp_server", "--root", root],
        "cwd": project_root,
        "env": {"WIKI_ROOT": root, "WIKI_LOG_LEVEL": "INFO"},
    }
else:
    server = {
        "type": "streamable-http",
        "url": url,
        "headers": {"Authorization": f"Bearer {token}"},
    }
(output / "references" / "mcp-config.json").write_text(
    json.dumps({"mcpServers": {name: server}}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

cli = shlex.quote(str(Path(project_root) / "scripts" / "wiki.sh"))
quoted_root = shlex.quote(root)

connection_instruction = (
    "Use the local MCP stdio configuration in `references/mcp-config.json`. "
    "If MCP tools are unavailable, use the local CLI examples below."
    if mode == "local"
    else
    "Use the Streamable HTTPS MCP configuration in `references/mcp-config.json`. "
    "The server requires the Bearer token stored in the protected connection files."
)

skill = f'''---
name: {name}
description: {json.dumps(description, ensure_ascii=False)}
compatibility: "MCP client or local Python 3.10+"
metadata:
  generated-by: "llm-wiki-kiss"
  connection-mode: "{mode}"
---

# {label} — private wiki

This skill connects to one private, single-tenant wiki-kiss knowledge base.
Use it whenever the user asks to consult, search, update, or remember information
in **{label}**.

## Security rules

1. Read `references/connection.json` only when connection details are needed.
2. Never print, quote, summarize, log, or reveal `bearer_token`.
3. Never copy the connection files into project output or version control.
4. Do not send wiki content to endpoints other than the configured MCP URL.
5. Treat every path as relative to the configured wiki root; never use `..`.

## Connection

{connection_instruction}

- Mode: `{mode}`
- Connection metadata: `references/connection.json`
- Ready-to-adapt MCP client config: `references/mcp-config.json`

The local filesystem path in the connection metadata is valid only on the wiki
host. Remote agents must use the HTTPS URL and must not attempt direct filesystem
access.

## Available MCP tools

- `list_pages`: discover pages, optionally under `subdir`.
- `read_page`: read one Markdown/HTML page by relative `path`.
- `search`: search text before deciding what to read or write.
- `write_page`: create or replace a complete page.
- `append_note`: append a timestamped note or daily log entry.

## Required workflow

1. Search or list before reading.
2. Read an existing page before overwriting it.
3. Prefer `overwrite=false` for new pages.
4. Use `append_note` for quick memories and operational logs.
5. Cite source page paths in answers based on wiki content.
6. If information is absent, say so instead of inventing it.

## Local CLI fallback

Use this only when running on the same machine as the wiki:

```bash
{cli} --root {quoted_root} list
{cli} --root {quoted_root} search "query"
{cli} --root {quoted_root} read notes/example.md
```

CLI and MCP stdio do not use the network. HTTPS access must use only the URL and
token from the protected references.
'''
(output / "SKILL.md").write_text(skill, encoding="utf-8")
PY

find "${TEMPORARY}" -type d -exec chmod 700 {} +
find "${TEMPORARY}" -type f -exec chmod 600 {} +

if [[ -d "${DESTINATION}" ]]; then
  backup="${TARGET}/.${NAME}.old.$$"
  mv "${DESTINATION}" "${backup}"
  mv "${TEMPORARY}" "${DESTINATION}"
  rm -rf "${backup}"
else
  mv "${TEMPORARY}" "${DESTINATION}"
fi
trap - EXIT

log_ok "Skill generated: ${DESTINATION}"
log_info "Mode: ${MODE}"
log_info "Wiki root: ${WIKI_ROOT}"
if [[ "${MODE}" == "https" ]]; then
  log_info "URL MCP: ${WIKI_MCP_URL}"
fi
log_warn "The skill contains credentials: do not commit or share it."
printf 'SKILL_PATH=%s\n' "${DESTINATION}/SKILL.md"
