#!/usr/bin/env bash
# Crea (o ripristina) l'ambiente virtuale e installa le dipendenze del progetto.
set -euo pipefail

_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${_LIB}/lib.sh"

usage() {
  cat <<EOF
${C_BOLD}Uso:${C_RESET} scripts/setup.sh [opzioni]

Crea l'ambiente virtuale Python, installa le dipendenze e prepara la
cartella var/ per log e pid dei servizi.

Opzioni:
  --recreate       Ricrea il venv da zero (cancella .venv esistente)
  --with-dev       Installa anche le dipendenze di sviluppo (pytest, ruff)
  --no-pip         Salta l'upgrade di pip
  -h, --help       Mostra questo messaggio
EOF
}

RECREATE=0
WITH_DEV=0
NO_PIP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --recreate) RECREATE=1 ;;
    --with-dev) WITH_DEV=1 ;;
    --no-pip)   NO_PIP=1 ;;
    -h|--help)  usage; exit 0 ;;
    *) log_error "Argomento sconosciuto: $1"; usage; exit 2 ;;
  esac
  shift
done

load_env_file
ensure_dirs

if [[ "${RECREATE}" -eq 1 && -d "${VENV_DIR}" ]]; then
  log_step "Ricreo l'ambiente virtuale"
  rm -rf "${VENV_DIR}"
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  log_step "Creo l'ambiente virtuale in ${VENV_DIR}"
  PY="$(resolve_python_for_venv)"
  log_info "Uso interprete: ${PY}"
  "${PY}" -m venv "${VENV_DIR}"
else
  log_info "Ambiente virtuale esistente: ${VENV_DIR}"
fi

if [[ "${NO_PIP}" -eq 0 ]]; then
  log_step "Aggiorno pip"
  "${VENV_PYTHON}" -m pip install --upgrade pip wheel setuptools >/dev/null
fi

log_step "Installo dipendenze di base"
"${VENV_PYTHON}" -m pip install -r "${PROJECT_ROOT}/requirements.txt"

if [[ "${WITH_DEV}" -eq 1 ]]; then
  log_step "Installo dipendenze di sviluppo"
  "${VENV_PYTHON}" -m pip install -r "${PROJECT_ROOT}/requirements-dev.txt"
fi

log_step "Verifico l'installazione"
"${VENV_PYTHON}" -c "import mcp, fastapi, uvicorn, pydantic; print('mcp', mcp.__version__)"
"${VENV_PYTHON}" -c "import wiki_core, mcp_server, rest_api; print('moduli OK')"

log_ok "Setup completato."
log_info "Attiva il venv con: source ${VENV_DIR}/bin/activate"
