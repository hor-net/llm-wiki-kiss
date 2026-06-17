#!/usr/bin/env bash
# Funzioni condivise per gli script del progetto llm-wiki-kiss.
# Questo file viene "sourced" dagli altri script. Non eseguirlo direttamente.

set -euo pipefail

# ----------------------------------------------------------------------
# Risoluzione percorsi
# ----------------------------------------------------------------------

_LIB_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${_LIB_SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
VENV_PYTHON="${VENV_DIR}/bin/python"
WIKI_DIR="${PROJECT_ROOT}/wiki"
VAR_DIR="${PROJECT_ROOT}/var"
RUN_DIR="${VAR_DIR}/run"
LOG_DIR="${VAR_DIR}/log"

PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTHON_MIN_VERSION="${PYTHON_MIN_VERSION:-3.10}"
DEFAULT_HOST="${DEFAULT_HOST:-127.0.0.1}"
DEFAULT_PORT="${DEFAULT_PORT:-8765}"

# ----------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------

_COLOR=1
if [[ -n "${NO_COLOR:-}" || ! -t 1 ]]; then
  _COLOR=0
fi

if [[ "${_COLOR}" -eq 1 ]]; then
  C_RESET=$'\033[0m'
  C_BOLD=$'\033[1m'
  C_DIM=$'\033[2m'
  C_RED=$'\033[31m'
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_BLUE=$'\033[34m'
  C_CYAN=$'\033[36m'
else
  C_RESET=""
  C_BOLD=""
  C_DIM=""
  C_RED=""
  C_GREEN=""
  C_YELLOW=""
  C_BLUE=""
  C_CYAN=""
fi

log_info()    { printf "%s[INFO]%s %s\n"    "${C_BLUE}"   "${C_RESET}" "$*"; }
log_ok()      { printf "%s[ OK ]%s %s\n"    "${C_GREEN}"  "${C_RESET}" "$*"; }
log_warn()    { printf "%s[WARN]%s %s\n"    "${C_YELLOW}" "${C_RESET}" "$*" >&2; }
log_error()   { printf "%s[FAIL]%s %s\n"    "${C_RED}"    "${C_RESET}" "$*" >&2; }
log_step()    { printf "\n%s==>%s %s\n"     "${C_CYAN}${C_BOLD}" "${C_RESET}" "$*"; }

# ----------------------------------------------------------------------
# Ambiente
# ----------------------------------------------------------------------

ensure_dirs() {
  mkdir -p "${WIKI_DIR}" "${VAR_DIR}" "${RUN_DIR}" "${LOG_DIR}"
}

# Carica variabili d'ambiente da .env o .wiki-kiss.env se presenti.
load_env_file() {
  local f
  for f in "${PROJECT_ROOT}/.wiki-kiss.env" "${PROJECT_ROOT}/.env"; do
    if [[ -f "${f}" ]]; then
      log_info "Carico variabili da ${f}"
      # Esporta solo righe KEY=VALUE (no export obbligatorio, no commenti).
      set -a
      # shellcheck disable=SC1090
      source "${f}"
      set +a
    fi
  done
}

require_venv() {
  if [[ ! -x "${VENV_PYTHON}" ]]; then
    log_error "Ambiente virtuale non trovato: ${VENV_PYTHON}"
    log_error "Esegui prima: scripts/setup.sh"
    return 1
  fi
  "${VENV_PYTHON}" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" \
    || { log_error "Python 3.10+ richiesto"; return 1; }
}

detect_wiki_root() {
  if [[ -n "${WIKI_ROOT:-}" ]]; then
    printf "%s" "${WIKI_ROOT}"
  else
    printf "%s" "${WIKI_DIR}"
  fi
}

resolve_python_for_venv() {
  if command -v python3.12 >/dev/null 2>&1; then
    printf "%s" "python3.12"
  elif command -v python3.11 >/dev/null 2>&1; then
    printf "%s" "python3.11"
  elif command -v python3.10 >/dev/null 2>&1; then
    printf "%s" "python3.10"
  elif command -v python3.13 >/dev/null 2>&1; then
    printf "%s" "python3.13"
  elif command -v python3 >/dev/null 2>&1; then
    printf "%s" "python3"
  else
    log_error "Nessun interprete Python trovato nel PATH"
    return 1
  fi
}

# ----------------------------------------------------------------------
# Servizi
# ----------------------------------------------------------------------

pidfile_for() {
  printf "%s/%s.pid" "${RUN_DIR}" "$1"
}

is_running() {
  local name="$1"
  local pf
  pf="$(pidfile_for "${name}")"
  [[ -f "${pf}" ]] || return 1
  local pid
  pid="$(cat "${pf}" 2>/dev/null || true)"
  [[ -n "${pid}" ]] || return 1
  kill -0 "${pid}" 2>/dev/null
}

start_daemon() {
  local name="$1"; shift
  local pf
  pf="$(pidfile_for "${name}")"
  if is_running "${name}"; then
    log_warn "${name} è già in esecuzione (pid $(cat "${pf}"))"
    return 0
  fi
  ensure_dirs
  local logf="${LOG_DIR}/${name}.log"
  log_info "Avvio ${name} in background (log: ${logf})"
  (
    cd "${PROJECT_ROOT}"
    "$@" >>"${logf}" 2>&1 &
    echo $! >"${pf}"
  )
  sleep 0.4
  if is_running "${name}"; then
    log_ok "${name} avviato (pid $(cat "${pf}"))"
  else
    log_error "Avvio di ${name} fallito; controlla ${logf}"
    return 1
  fi
}

stop_service() {
  local name="$1"
  local pf
  pf="$(pidfile_for "${name}")"
  if ! [[ -f "${pf}" ]]; then
    log_warn "${name} non è in esecuzione"
    return 0
  fi
  local pid
  pid="$(cat "${pf}" 2>/dev/null || true)"
  if [[ -z "${pid}" ]] || ! kill -0 "${pid}" 2>/dev/null; then
    log_warn "${name}: pidfile stantio, lo rimuovo"
    rm -f "${pf}"
    return 0
  fi
  log_info "Arresto ${name} (pid ${pid})"
  kill "${pid}" 2>/dev/null || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 "${pid}" 2>/dev/null || break
    sleep 0.3
  done
  if kill -0 "${pid}" 2>/dev/null; then
    log_warn "${name} non risponde, invio SIGKILL"
    kill -9 "${pid}" 2>/dev/null || true
  fi
  rm -f "${pf}"
  log_ok "${name} arrestato"
}

print_status_line() {
  local name="$1"
  local desc="$2"
  if is_running "${name}"; then
    local pid
    pid="$(cat "$(pidfile_for "${name}")")"
    printf "  %s%-12s%s %s(pid %s)%s  %s\n" \
      "${C_GREEN}" "running" "${C_RESET}" "${C_DIM}" "${pid}" "${C_RESET}" "${desc}"
  else
    printf "  %s%-12s%s %s\n" \
      "${C_DIM}" "stopped" "${C_RESET}" "${desc}"
  fi
}
