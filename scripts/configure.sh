#!/usr/bin/env bash
# Configura root, token e interfaccia MCP HTTPS del wiki single-tenant.
set -euo pipefail

_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${_LIB}/lib.sh"

CONFIG_FILE="${WIKI_CONFIG_FILE:-${PROJECT_ROOT}/.wiki-kiss.env}"

usage() {
  cat <<EOF
${C_BOLD}Uso:${C_RESET} scripts/configure.sh [opzioni]

Senza opzioni avvia la configurazione interattiva. Le impostazioni vengono
salvate in .wiki-kiss.env con permessi 600.

Opzioni:
  --root PATH          Root del singolo wiki; viene creata se manca
  --token TOKEN        Imposta un token esistente (sconsigliato nella shell history)
  --rotate-token       Genera e salva un nuovo token casuale
  --show-token         Stampa il token configurato e termina
  --https on|off       Abilita/avvia oppure arresta/disabilita MCP HTTPS
  --host HOST          Host HTTPS (default: 127.0.0.1)
  --port PORT          Porta HTTPS (default: 8766)
  --url URL            URL pubblica MCP, es. https://wiki.example.com/mcp
  --cert PATH          Certificato TLS PEM
  --key PATH           Chiave privata TLS PEM
  --no-apply           Salva senza avviare o arrestare il servizio
  -h, --help           Mostra questo messaggio

Esempi:
  scripts/configure.sh --root ~/wiki-privato --https off
  scripts/configure.sh --rotate-token
  scripts/configure.sh --https on --cert /etc/tls/wiki.crt --key /etc/tls/wiki.key
  scripts/configure.sh --https off
  scripts/configure.sh --show-token
EOF
}

had_arguments=$#
ROOT_ARG=""
TOKEN_ARG=""
HTTPS_ARG=""
HOST_ARG=""
PORT_ARG=""
URL_ARG=""
CERT_ARG=""
KEY_ARG=""
ROTATE_TOKEN=0
SHOW_TOKEN=0
APPLY=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)         ROOT_ARG="$2"; shift 2 ;;
    --token)        TOKEN_ARG="$2"; shift 2 ;;
    --rotate-token) ROTATE_TOKEN=1; shift ;;
    --show-token)   SHOW_TOKEN=1; shift ;;
    --https)        HTTPS_ARG="$2"; shift 2 ;;
    --host)         HOST_ARG="$2"; shift 2 ;;
    --port)         PORT_ARG="$2"; shift 2 ;;
    --url)          URL_ARG="$2"; shift 2 ;;
    --cert)         CERT_ARG="$2"; shift 2 ;;
    --key)          KEY_ARG="$2"; shift 2 ;;
    --no-apply)     APPLY=0; shift ;;
    -h|--help)      usage; exit 0 ;;
    *) log_error "Argomento sconosciuto: $1"; usage; exit 2 ;;
  esac
done

if [[ "${SHOW_TOKEN}" -eq 1 && -f "${CONFIG_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"
  set +a
elif [[ "${CONFIG_FILE}" == "${PROJECT_ROOT}/.wiki-kiss.env" ]]; then
  load_env_file
elif [[ -f "${CONFIG_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"
  set +a
fi

ROOT_VALUE="${ROOT_ARG:-${WIKI_ROOT:-${WIKI_DIR}}}"
TOKEN_VALUE="${TOKEN_ARG:-${WIKI_MCP_TOKEN:-}}"
HTTPS_VALUE="${HTTPS_ARG:-${WIKI_HTTPS_ENABLED:-0}}"
HOST_VALUE="${HOST_ARG:-${WIKI_HTTP_HOST:-127.0.0.1}}"
PORT_VALUE="${PORT_ARG:-${WIKI_HTTP_PORT:-8766}}"
URL_VALUE="${URL_ARG:-${WIKI_MCP_URL:-}}"
CERT_VALUE="${CERT_ARG:-${WIKI_TLS_CERT:-}}"
KEY_VALUE="${KEY_ARG:-${WIKI_TLS_KEY:-}}"

if [[ "${SHOW_TOKEN}" -eq 1 ]]; then
  if [[ -z "${TOKEN_VALUE}" ]]; then
    log_error "Nessun token configurato."
    exit 1
  fi
  printf '%s\n' "${TOKEN_VALUE}"
  exit 0
fi

if [[ "${had_arguments}" -eq 0 && -t 0 ]]; then
  printf 'Root del wiki [%s]: ' "${ROOT_VALUE}"
  read -r answer
  ROOT_VALUE="${answer:-${ROOT_VALUE}}"

  printf 'Abilitare e avviare MCP HTTPS? [s/N]: '
  read -r answer
  case "${answer}" in
    s|S|si|SI|sì|SÌ|y|Y|yes|YES) HTTPS_VALUE=1 ;;
    *) HTTPS_VALUE=0 ;;
  esac

  if [[ "${HTTPS_VALUE}" == "1" ]]; then
    printf 'Certificato TLS PEM [%s]: ' "${CERT_VALUE}"
    read -r answer
    CERT_VALUE="${answer:-${CERT_VALUE}}"
    printf 'Chiave privata TLS PEM [%s]: ' "${KEY_VALUE}"
    read -r answer
    KEY_VALUE="${answer:-${KEY_VALUE}}"
  fi
fi

case "${HTTPS_VALUE}" in
  on|ON|true|TRUE|yes|YES|1) HTTPS_VALUE=1 ;;
  off|OFF|false|FALSE|no|NO|0) HTTPS_VALUE=0 ;;
  *) log_error "Valore --https non valido: usa on oppure off."; exit 2 ;;
esac

ROOT_VALUE="${ROOT_VALUE/#\~/${HOME}}"
CERT_VALUE="${CERT_VALUE/#\~/${HOME}}"
KEY_VALUE="${KEY_VALUE/#\~/${HOME}}"

if [[ ! "${PORT_VALUE}" =~ ^[0-9]+$ ]] \
   || (( PORT_VALUE < 1 || PORT_VALUE > 65535 )); then
  log_error "Porta non valida: ${PORT_VALUE}"
  exit 2
fi

mkdir -p -m 700 "${ROOT_VALUE}"
ROOT_VALUE="$(cd "${ROOT_VALUE}" && pwd -P)"

resolve_existing_file() {
  local raw="$1"
  local label="$2"
  if [[ -z "${raw}" ]]; then
    log_error "${label} mancante."
    return 1
  fi
  if [[ ! -f "${raw}" || ! -r "${raw}" ]]; then
    log_error "${label} non leggibile: ${raw}"
    return 1
  fi
  (cd "$(dirname "${raw}")" && printf '%s/%s' "$(pwd -P)" "$(basename "${raw}")")
}

generate_token() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
    return
  fi
  "${PYTHON_BIN}" -c 'import secrets; print(secrets.token_hex(32))'
}

if [[ "${ROTATE_TOKEN}" -eq 1 || -z "${TOKEN_VALUE}" ]]; then
  TOKEN_VALUE="$(generate_token)"
fi
if [[ -z "${TOKEN_VALUE//[[:space:]]/}" ]]; then
  log_error "Il token non può essere vuoto."
  exit 2
fi

if [[ -n "${CERT_VALUE}" ]]; then
  CERT_VALUE="$(resolve_existing_file "${CERT_VALUE}" "Certificato TLS")"
fi
if [[ -n "${KEY_VALUE}" ]]; then
  KEY_VALUE="$(resolve_existing_file "${KEY_VALUE}" "Chiave TLS")"
fi
if [[ "${HTTPS_VALUE}" -eq 1 && ( -z "${CERT_VALUE}" || -z "${KEY_VALUE}" ) ]]; then
  log_error "Per abilitare HTTPS servono --cert e --key in formato PEM."
  exit 2
fi
if [[ "${HTTPS_VALUE}" -eq 1 && -z "${URL_VALUE}" ]]; then
  case "${HOST_VALUE}" in
    0.0.0.0|::)
      log_error "Con host ${HOST_VALUE} devi specificare --url con il nome pubblico."
      exit 2
      ;;
    *) URL_VALUE="https://${HOST_VALUE}:${PORT_VALUE}/mcp" ;;
  esac
fi
if [[ -n "${URL_VALUE}" && ! "${URL_VALUE}" =~ ^https://[^[:space:]]+/mcp/?$ ]]; then
  log_error "URL MCP non valida: deve essere https://.../mcp"
  exit 2
fi

umask 077
mkdir -p "$(dirname "${CONFIG_FILE}")"
temporary="$(mktemp "${CONFIG_FILE}.tmp.XXXXXX")"
cleanup() { rm -f "${temporary}"; }
trap cleanup EXIT
{
  printf '# Generato da scripts/configure.sh — non committare.\n'
  printf 'WIKI_ROOT=%q\n' "${ROOT_VALUE}"
  printf 'WIKI_MCP_TOKEN=%q\n' "${TOKEN_VALUE}"
  printf 'WIKI_HTTPS_ENABLED=%q\n' "${HTTPS_VALUE}"
  printf 'WIKI_HTTP_HOST=%q\n' "${HOST_VALUE}"
  printf 'WIKI_HTTP_PORT=%q\n' "${PORT_VALUE}"
  printf 'WIKI_MCP_URL=%q\n' "${URL_VALUE}"
  printf 'WIKI_TLS_CERT=%q\n' "${CERT_VALUE}"
  printf 'WIKI_TLS_KEY=%q\n' "${KEY_VALUE}"
} >"${temporary}"
chmod 600 "${temporary}"
mv -f "${temporary}" "${CONFIG_FILE}"
trap - EXIT

log_ok "Configurazione salvata: ${CONFIG_FILE}"
log_info "Root wiki: ${ROOT_VALUE}"
log_info "MCP HTTPS: $([[ "${HTTPS_VALUE}" -eq 1 ]] && printf 'abilitato' || printf 'disabilitato')"
[[ -n "${URL_VALUE}" ]] && log_info "URL MCP: ${URL_VALUE}"
printf 'WIKI_MCP_TOKEN=%s\n' "${TOKEN_VALUE}"

if [[ "${APPLY}" -eq 1 ]]; then
  REST_WAS_RUNNING=0
  if is_running "rest"; then
    REST_WAS_RUNNING=1
    stop_service "rest"
  fi
  if is_running "mcp-http"; then
    stop_service "mcp-http"
  fi
  if [[ "${REST_WAS_RUNNING}" -eq 1 ]]; then
    "${PROJECT_ROOT}/scripts/start-rest.sh"
  fi
  if [[ "${HTTPS_VALUE}" -eq 1 ]]; then
    "${PROJECT_ROOT}/scripts/start-mcp-http.sh"
  else
    log_info "Interfaccia MCP HTTPS spenta. MCP stdio e CLI restano disponibili."
  fi
fi
