#!/usr/bin/env bash
# Avvia il server MCP (stdio) per il wiki KISS.
set -euo pipefail

_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${_LIB}/lib.sh"

usage() {
  cat <<EOF
${C_BOLD}Uso:${C_RESET} scripts/start-mcp.sh [opzioni]

Avvia il server MCP del wiki KISS. Il server comunica via stdio e DEVE
essere lanciato come sottoprocesso di un client MCP (Claude Code, Claude
Desktop, Open Cloud, Perplexity, ...). Lanciarlo a mano è utile solo
per test: in quel caso usare --foreground.

Opzioni:
  --root PATH         Cartella wiki (default: ./wiki o \$WIKI_ROOT)
  --log-level LEVEL   Livello di log (default: INFO)
  -h, --help          Mostra questo messaggio

Per configurare un client MCP, usare:
  scripts/install-mcp-client.sh --client claude-code
EOF
}

ROOT_ARG=""
LOG_LEVEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)        ROOT_ARG="$2"; shift 2 ;;
    --log-level)   LOG_LEVEL="$2"; shift 2 ;;
    -h|--help)     usage; exit 0 ;;
    *) log_error "Argomento sconosciuto: $1"; usage; exit 2 ;;
  esac
done

load_env_file
require_venv

ROOT_FLAG=()
if [[ -n "${ROOT_ARG}" ]]; then
  ROOT_FLAG=(--root "${ROOT_ARG}")
fi
LEVEL_FLAG=()
if [[ -n "${LOG_LEVEL}" ]]; then
  LEVEL_FLAG=(--log-level "${LOG_LEVEL}")
fi

# Modalità foreground: il client MCP usa questo script come comando.
# Questa è l'unica modalità realistica per stdio.
exec "${VENV_PYTHON}" -m mcp_server \
  ${ROOT_FLAG[@]+"${ROOT_FLAG[@]}"} \
  ${LEVEL_FLAG[@]+"${LEVEL_FLAG[@]}"}
