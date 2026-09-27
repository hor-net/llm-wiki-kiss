#!/usr/bin/env bash
# Avvia il server MCP Streamable HTTP protetto da TLS (HTTPS).
set -euo pipefail

_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${_LIB}/lib.sh"

usage() {
  cat <<EOF
${C_BOLD}Uso:${C_RESET} scripts/start-mcp-http.sh [opzioni]

Avvia il server MCP con trasporto Streamable HTTPS (MCP 2025-06-18).
The start is allowed only if configure.sh enabled HTTPS and a
certificate, private key and Bearer token are present.

Opzioni:
  --host HOST           Host di binding (default: 127.0.0.1)
  --port PORT           Porta di ascolto (default: 8766)
  --root PATH           Cartella wiki (default: ./wiki o \$WIKI_ROOT)
  --token TOKEN         Bearer token obbligatorio (default: \$WIKI_MCP_TOKEN)
  --cert PATH           Certificato TLS PEM (default: \$WIKI_TLS_CERT)
  --key PATH            Chiave privata TLS PEM (default: \$WIKI_TLS_KEY)
  --workers N           Worker uvicorn (default: 1).
  --log-level LEVEL     Livello di log (default: INFO).
  --foreground, -f      Avvia in foreground.
  -h, --help            Mostra questo messaggio.

Variabili d'ambiente riconosciute:
  WIKI_ROOT, WIKI_MCP_TOKEN, WIKI_HTTPS_ENABLED, WIKI_HTTP_HOST,
  WIKI_HTTP_PORT, WIKI_TLS_CERT, WIKI_TLS_KEY
EOF
}

HOST_ARG=""
PORT_ARG=""
ROOT_ARG=""
TOKEN_ARG=""
CERT_ARG=""
KEY_ARG=""
WORKERS=1
LOG_LEVEL=""
FOREGROUND=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)        HOST_ARG="$2"; shift 2 ;;
    --port)        PORT_ARG="$2"; shift 2 ;;
    --root)        ROOT_ARG="$2"; shift 2 ;;
    --token)       TOKEN_ARG="$2"; shift 2 ;;
    --cert)        CERT_ARG="$2"; shift 2 ;;
    --key)         KEY_ARG="$2"; shift 2 ;;
    --workers)     WORKERS="$2"; shift 2 ;;
    --log-level)   LOG_LEVEL="$2"; shift 2 ;;
    -f|--foreground) FOREGROUND=1; shift ;;
    -h|--help)     usage; exit 0 ;;
    *) log_error "Argomento sconosciuto: $1"; usage; exit 2 ;;
  esac
done

load_env_file
require_venv

HOST="${HOST_ARG:-${WIKI_HTTP_HOST:-127.0.0.1}}"
PORT="${PORT_ARG:-${WIKI_HTTP_PORT:-8766}}"
CERT="${CERT_ARG:-${WIKI_TLS_CERT:-}}"
KEY="${KEY_ARG:-${WIKI_TLS_KEY:-}}"

if [[ "${WIKI_HTTPS_ENABLED:-0}" != "1" ]]; then
  log_error "Interfaccia MCP HTTPS disabilitata. Usa: scripts/configure.sh --https on"
  exit 2
fi
if [[ -z "${CERT}" || ! -r "${CERT}" ]]; then
  log_error "TLS certificate missing or not readable: ${CERT:-<empty>}"
  exit 2
fi
if [[ -z "${KEY}" || ! -r "${KEY}" ]]; then
  log_error "TLS key missing or not readable: ${KEY:-<empty>}"
  exit 2
fi

# Controlla che la porta sia libera prima di partire.
if command -v lsof >/dev/null 2>&1; then
  if lsof -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    log_error "Port ${PORT} is already in use."
    exit 1
  fi
fi

export WIKI_ROOT="${ROOT_ARG:-${WIKI_ROOT:-$(detect_wiki_root)}}"
[[ -n "${TOKEN_ARG}" ]] && export WIKI_MCP_TOKEN="${TOKEN_ARG}"
if [[ -z "${WIKI_MCP_TOKEN:-}" ]]; then
  log_error "Bearer token obbligatorio: usa --token o WIKI_MCP_TOKEN."
  exit 2
fi
[[ -n "${LOG_LEVEL}" ]] && export WIKI_LOG_LEVEL="${LOG_LEVEL}"

UV_FLAGS=(
  "mcp_server.http:app"
  "--host" "${HOST}"
  "--port" "${PORT}"
  "--workers" "${WORKERS}"
  "--log-level" "${WIKI_LOG_LEVEL:-info}"
  "--ssl-certfile" "${CERT}"
  "--ssl-keyfile" "${KEY}"
)

if [[ "${FOREGROUND}" -eq 1 ]]; then
  exec "${VENV_PYTHON}" -m uvicorn "${UV_FLAGS[@]}"
fi

start_daemon "mcp-http" "${VENV_PYTHON}" -m uvicorn "${UV_FLAGS[@]}"
log_info "Server MCP Streamable HTTPS in ascolto su https://${HOST}:${PORT}"
log_info "Endpoint MCP: https://${HOST}:${PORT}/mcp"
log_info "Health check: https://${HOST}:${PORT}/health"
log_info "Autenticazione Bearer ATTIVA"
log_info "Ferma con: scripts/stop.sh mcp-http"
