#!/usr/bin/env bash
# Avvia il server MCP Streamable HTTP (per client MCP in cloud).
set -euo pipefail

_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${_LIB}/lib.sh"

usage() {
  cat <<EOF
${C_BOLD}Uso:${C_RESET} scripts/start-mcp-http.sh [opzioni]

Avvia il server MCP con trasporto Streamable HTTP (MCP 2025-06-18).
Permette a client MCP in cloud (Open Cloud aggiornato, client MCP-aware)
di connettersi via HTTPS con autenticazione Bearer.

Opzioni:
  --host HOST           Host di binding (default: 127.0.0.1)
  --port PORT           Porta di ascolto (default: 8766)
  --root PATH           Cartella wiki (default: ./wiki o \$WIKI_ROOT)
  --mcp-path PATH       Endpoint MCP (default: /mcp)
  --token TOKEN         Bearer token (default: \$WIKI_MCP_TOKEN).
                        Se non impostato, autenticazione disabilitata.
  --stateless           Ogni richiesta è indipendente (default: true).
  --stateful            Mantieni sessioni MCP.
  --json-response       Rispondi con JSON puro (no SSE, default).
  --no-json-response    Rispondi con Server-Sent Events.
  --workers N           Worker uvicorn (default: 1).
  --log-level LEVEL     Livello di log (default: INFO).
  --foreground, -f      Avvia in foreground.
  -h, --help            Mostra questo messaggio.

Variabili d'ambiente riconosciute:
  WIKI_ROOT, WIKI_MCP_TOKEN, WIKI_HTTP_HOST, WIKI_HTTP_PORT, WIKI_MCP_PATH
EOF
}

HOST="${WIKI_HTTP_HOST:-127.0.0.1}"
PORT="${WIKI_HTTP_PORT:-8766}"
MCP_PATH="${WIKI_MCP_PATH:-/mcp}"
ROOT_ARG=""
TOKEN_ARG=""
STATELESS=1
JSON=1
WORKERS=1
LOG_LEVEL=""
FOREGROUND=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)        HOST="$2"; shift 2 ;;
    --port)        PORT="$2"; shift 2 ;;
    --root)        ROOT_ARG="$2"; shift 2 ;;
    --mcp-path)    MCP_PATH="$2"; shift 2 ;;
    --token)       TOKEN_ARG="$2"; shift 2 ;;
    --stateless)   STATELESS=1 ;;
    --stateful)    STATELESS=0 ;;
    --json-response) JSON=1 ;;
    --no-json-response) JSON=0 ;;
    --workers)     WORKERS="$2"; shift 2 ;;
    --log-level)   LOG_LEVEL="$2"; shift 2 ;;
    -f|--foreground) FOREGROUND=1 ;;
    -h|--help)     usage; exit 0 ;;
    *) log_error "Argomento sconosciuto: $1"; usage; exit 2 ;;
  esac
done

load_env_file
require_venv

# Controlla che la porta sia libera prima di partire.
if command -v lsof >/dev/null 2>&1; then
  if lsof -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    log_error "La porta ${PORT} è già occupata."
    exit 1
  fi
fi

export WIKI_ROOT="${ROOT_ARG:-${WIKI_ROOT:-$(detect_wiki_root)}}"
[[ -n "${TOKEN_ARG}" ]] && export WIKI_MCP_TOKEN="${TOKEN_ARG}"
[[ -n "${LOG_LEVEL}" ]] && export WIKI_LOG_LEVEL="${LOG_LEVEL}"

UV_FLAGS=(
  "mcp_server.http:app"
  "--host" "${HOST}"
  "--port" "${PORT}"
  "--workers" "${WORKERS}"
  "--log-level" "${WIKI_LOG_LEVEL:-info}"
)

if [[ "${FOREGROUND}" -eq 1 ]]; then
  exec "${VENV_PYTHON}" -m uvicorn "${UV_FLAGS[@]}"
fi

start_daemon "mcp-http" "${VENV_PYTHON}" -m uvicorn "${UV_FLAGS[@]}"
log_info "Server MCP Streamable HTTP in ascolto su http://${HOST}:${PORT}"
log_info "Endpoint MCP: http://${HOST}:${PORT}${MCP_PATH}"
log_info "Health check: http://${HOST}:${PORT}/health"
if [[ -n "${WIKI_MCP_TOKEN:-}" ]]; then
  log_info "Autenticazione Bearer ATTIVA"
else
  log_warn "Autenticazione Bearer DISATTIVATA (imposta WIKI_MCP_TOKEN per attivarla)"
fi
log_info "Ferma con: scripts/stop.sh mcp-http"
