#!/usr/bin/env bash
# Stampa (e opzionalmente scrive) la configurazione MCP per i client più diffusi.
set -euo pipefail

_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${_LIB}/lib.sh"

usage() {
  cat <<EOF
${C_BOLD}Uso:${C_RESET} scripts/install-mcp-client.sh [opzioni]

Genera il frammento di configurazione MCP da inserire nel file di
configurazione del proprio client (Claude Desktop, Claude Code,
Open Cloud, Perplexity, ...). Di default stampa su stdout.

Opzioni:
  --client NAME   Nome logico del client (claude-desktop, claude-code,
                  generic) - influenza solo il commento e la forma
                  dell'output. Default: generic.
  --root PATH     Cartella wiki. Default: ./wiki o \$WIKI_ROOT
  --python PATH   Interprete Python del venv (default: .venv/bin/python)
  --out FILE      Scrivi la configurazione su FILE invece di stdout
  -h, --help      Mostra questo messaggio
EOF
}

CLIENT="generic"
ROOT_ARG=""
PY_BIN=""
OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --client) CLIENT="$2"; shift 2 ;;
    --root)   ROOT_ARG="$2"; shift 2 ;;
    --python) PY_BIN="$2"; shift 2 ;;
    --out)    OUT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) log_error "Argomento sconosciuto: $1"; usage; exit 2 ;;
  esac
done

load_env_file

PY="${PY_BIN:-${VENV_PYTHON}}"
if [[ ! -x "${PY}" ]]; then
  log_warn "Python venv non trovato in ${PY}. Userò 'python'."
  PY="python"
fi

WIKI="${ROOT_ARG:-${WIKI_ROOT:-$(detect_wiki_root)}}"

# Costruisci il frammento in base al client.
emit() {
  cat <<EOF
{
  "mcpServers": {
    "wiki-kiss": {
      "command": "${PY}",
      "args": ["-m", "mcp_server", "--root", "${WIKI}"],
      "cwd": "${PROJECT_ROOT}",
      "env": {
        "WIKI_ROOT": "${WIKI}",
        "WIKI_LOG_LEVEL": "INFO"
      }
    }
  }
}
EOF
}

if [[ -n "${OUT}" ]]; then
  emit > "${OUT}"
  log_ok "Configurazione scritta in ${OUT}"
  exit 0
fi

case "${CLIENT}" in
  claude-desktop)
    log_info "Claude Desktop: incolla in ~/Library/Application Support/Claude/claude_desktop_config.json"
    ;;
  claude-code)
    log_info "Claude Code: incolla nella sezione 'mcpServers' del file .mcp.json del progetto"
    ;;
  generic|*)
    log_info "Configurazione generica MCP (stdio):"
    ;;
esac
echo
emit
