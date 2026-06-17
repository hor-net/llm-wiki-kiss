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
  --recreate         Ricrea il venv da zero (cancella .venv esistente)
  --with-dev         Installa anche le dipendenze di sviluppo (pytest, ruff)
  --no-pip           Salta l'upgrade di pip
  --bootstrap-pip    Se pip manca nel venv, prova a installarlo con
                     ensurepip (poi get-pip.py da PyPA). Vedi note sotto.
  -h, --help         Mostra questo messaggio

${C_BOLD}Note:${C_RESET}
Il venv potrebbe essere creato SENZA pip su sistemi Debian/Ubuntu dove
manca python3-pip, oppure su hosting con cPanel/DirectAdmin dove
ensurepip è disabilitato. In questi casi:

  * Python 3.10-3.13:  python3 -m ensurepip --upgrade
  * Se anche ensurepip fallisce: curl -sSL \\
      https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py \\
      && .venv/bin/python /tmp/get-pip.py
  * Oppure usa --bootstrap-pip per tentare automaticamente i passi
    precedenti prima di fallire.
EOF
}

RECREATE=0
WITH_DEV=0
NO_PIP=0
BOOTSTRAP_PIP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --recreate) RECREATE=1 ;;
    --with-dev) WITH_DEV=1 ;;
    --no-pip)   NO_PIP=1 ;;
    --bootstrap-pip) BOOTSTRAP_PIP=1 ;;
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

# ----------------------------------------------------------------------
# Verifica / bootstrap di pip
# ----------------------------------------------------------------------

ensure_pip() {
  # Se pip è disponibile, non fare nulla.
  if "${VENV_PYTHON}" -m pip --version >/dev/null 2>&1; then
    return 0
  fi
  log_warn "pip non disponibile nel venv. Tentativo di bootstrap..."
  # 1) Prova con ensurepip (funziona su Ubuntu/Debian recenti)
  if "${VENV_PYTHON}" -m ensurepip --upgrade >/dev/null 2>&1; then
    log_ok "pip installato tramite ensurepip"
    return 0
  fi
  # 2) Prova con get-pip.py da PyPA (richiede rete + write in /tmp)
  if command -v curl >/dev/null 2>&1; then
    local get_pip
    get_pip="$(mktemp -t get-pip-XXXXXX.py)"
    if curl -fsSL -o "${get_pip}" https://bootstrap.pypa.io/get-pip.py \
       && "${VENV_PYTHON}" "${get_pip}" >/dev/null 2>&1; then
      rm -f "${get_pip}"
      log_ok "pip installato tramite get-pip.py"
      return 0
    fi
    rm -f "${get_pip}"
  fi
  # 3) wget come alternativa
  if command -v wget >/dev/null 2>&1; then
    local get_pip
    get_pip="$(mktemp -t get-pip-XXXXXX.py)"
    if wget -q -O "${get_pip}" https://bootstrap.pypa.io/get-pip.py \
       && "${VENV_PYTHON}" "${get_pip}" >/dev/null 2>&1; then
      rm -f "${get_pip}"
      log_ok "pip installato tramite get-pip.py (wget)"
      return 0
    fi
    rm -f "${get_pip}"
  fi
  return 1
}

if [[ "${NO_PIP}" -eq 0 ]]; then
  if ! ensure_pip; then
    if [[ "${BOOTSTRAP_PIP}" -eq 1 ]]; then
      log_error "Bootstrap di pip fallito. Vedi sopra per le istruzioni."
    else
      log_error "pip non disponibile nel venv."
      log_error "Risolvi con: scripts/setup.sh --bootstrap-pip"
      log_error "oppure:    python3 -m ensurepip --upgrade  (con il venv attivo)"
      log_error "oppure:    curl -sSL https://bootstrap.pypa.io/get-pip.py | .venv/bin/python"
    fi
    exit 1
  fi
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
"${VENV_PYTHON}" -c "import mcp, fastapi, uvicorn, pydantic; print('mcp, fastapi, uvicorn, pydantic importati')"
"${VENV_PYTHON}" -c "import wiki_core, mcp_server, mcp_server.http, rest_api; print('moduli applicativi OK')"

log_ok "Setup completato."
log_info "Attiva il venv con: source ${VENV_DIR}/bin/activate"
