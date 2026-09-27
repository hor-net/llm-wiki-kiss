#!/usr/bin/env bash
# Avvia l'API REST (FastAPI/Uvicorn) in background o foreground.
set -euo pipefail

_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${_LIB}/lib.sh"

usage() {
  cat <<EOF
${C_BOLD}Uso:${C_RESET} scripts/start-rest.sh [opzioni]

Avvia l'API REST del wiki KISS (uvicorn su FastAPI).

Opzioni:
  --host HOST          Host di binding (default: 127.0.0.1)
  --port PORT          Porta di ascolto (default: 8765)
  --root PATH          Cartella wiki (default: ./wiki o \$WIKI_ROOT)
  --token TOKEN        Bearer token obbligatorio (default: \$WIKI_MCP_TOKEN)
  --workers N          Numero di worker uvicorn (default: 1)
  --reload             Abilita auto-reload (solo sviluppo)
  --foreground, -f     Avvia in foreground
  -h, --help           Mostra questo messaggio

Variabili d'ambiente riconosciute:
  WIKI_ROOT, WIKI_MCP_TOKEN, DEFAULT_HOST, DEFAULT_PORT
EOF
}

HOST="${DEFAULT_HOST}"
PORT="${DEFAULT_PORT}"
ROOT_ARG=""
TOKEN_ARG=""
WORKERS=1
RELOAD=""
FOREGROUND=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)     HOST="$2"; shift 2 ;;
    --port)     PORT="$2"; shift 2 ;;
    --root)     ROOT_ARG="$2"; shift 2 ;;
    --token)    TOKEN_ARG="$2"; shift 2 ;;
    --workers)  WORKERS="$2"; shift 2 ;;
    --reload)   RELOAD="--reload" ;;
    -f|--foreground) FOREGROUND=1 ;;
    -h|--help)  usage; exit 0 ;;
    *) log_error "Argomento sconosciuto: $1"; usage; exit 2 ;;
  esac
done

load_env_file
require_venv

case "${HOST}" in
  127.0.0.1|localhost|::1) ;;
  *)
    log_error "La REST API è consentita solo in loopback. Per accesso remoto usa MCP HTTPS."
    exit 2
    ;;
esac

# Controlla che la porta sia libera prima di partire.
if command -v lsof >/dev/null 2>&1; then
  if lsof -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    log_error "La porta ${PORT} è già occupata."
    exit 1
  fi
fi

export WIKI_ROOT="${ROOT_ARG:-${WIKI_ROOT:-$(detect_wiki_root)}}"
[[ -n "${TOKEN_ARG}" ]] && export WIKI_MCP_TOKEN="${TOKEN_ARG}"
if [[ -z "${WIKI_MCP_TOKEN:-}" ]]; then
  log_error "Bearer token obbligatorio: usa --token o WIKI_MCP_TOKEN."
  exit 2
fi
UV_FLAGS=(
  "rest_api:app"
  "--host" "${HOST}"
  "--port" "${PORT}"
  "--workers" "${WORKERS}"
  "--log-level" "${WIKI_LOG_LEVEL:-info}"
)
if [[ -n "${RELOAD}" ]]; then
  UV_FLAGS+=("--reload")
fi

if [[ "${FOREGROUND}" -eq 1 ]]; then
  exec "${VENV_PYTHON}" -m uvicorn "${UV_FLAGS[@]}"
fi

start_daemon "rest" "${VENV_PYTHON}" -m uvicorn "${UV_FLAGS[@]}"
log_info "API REST in ascolto su http://${HOST}:${PORT}"
log_info "Documentazione OpenAPI autenticata: http://${HOST}:${PORT}/docs"
log_info "Autenticazione Bearer ATTIVA"
log_info "Ferma con: scripts/stop.sh rest"
