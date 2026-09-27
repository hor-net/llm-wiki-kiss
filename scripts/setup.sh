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
  --root PATH        Configura la root del wiki
  --token TOKEN      Usa questo token invece di generarne uno
  --https on|off     Configura e applica lo stato dell'interfaccia MCP HTTPS
  --host HOST        Host MCP HTTPS (default: 127.0.0.1)
  --port PORT        Porta MCP HTTPS (default: 8766)
  --url URL          URL pubblica MCP, es. https://wiki.example.com/mcp
  --cert PATH        Certificato TLS PEM (necessario con --https on)
  --key PATH         Chiave TLS PEM (necessaria con --https on)
  --no-config        Non creare o aggiornare .wiki-kiss.env
  -h, --help         Mostra questo messaggio

${C_BOLD}Note:${C_RESET}
The venv may be created WITHOUT pip on Debian/Ubuntu systems where
python3-pip is missing, or on cPanel/DirectAdmin hosting where
ensurepip is disabled. In those cases:

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
CONFIG_ROOT=""
CONFIG_TOKEN=""
CONFIG_HTTPS=""
CONFIG_HOST=""
CONFIG_PORT=""
CONFIG_URL=""
CONFIG_CERT=""
CONFIG_KEY=""
CONFIGURE=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --recreate) RECREATE=1 ;;
    --with-dev) WITH_DEV=1 ;;
    --no-pip)   NO_PIP=1 ;;
    --bootstrap-pip) BOOTSTRAP_PIP=1 ;;
    --root)      CONFIG_ROOT="$2"; shift ;;
    --token)     CONFIG_TOKEN="$2"; shift ;;
    --https)     CONFIG_HTTPS="$2"; shift ;;
    --host)      CONFIG_HOST="$2"; shift ;;
    --port)      CONFIG_PORT="$2"; shift ;;
    --url)       CONFIG_URL="$2"; shift ;;
    --cert)      CONFIG_CERT="$2"; shift ;;
    --key)       CONFIG_KEY="$2"; shift ;;
    --no-config) CONFIGURE=0 ;;
    -h|--help)  usage; exit 0 ;;
    *) log_error "Unknown argument: $1"; usage; exit 2 ;;
  esac
  shift
done

load_env_file
ensure_dirs

if [[ "${RECREATE}" -eq 1 && -d "${VENV_DIR}" ]]; then
  log_step "Rebuilding the virtual environment"
  rm -rf "${VENV_DIR}"
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  log_step "Creating the virtual environment in ${VENV_DIR}"
  PY="$(resolve_python_for_venv)"
  log_info "Using interpreter: ${PY}"
  "${PY}" -m venv "${VENV_DIR}"
else
  log_info "Existing virtual environment: ${VENV_DIR}"
fi

# Verify the venv scaffold is complete: without bin/activate
# the venv is incomplete (e.g. python3-venv missing on Debian/Ubuntu).
if [[ ! -f "${VENV_DIR}/bin/activate" ]]; then
  log_error "Venv created without bin/activate: incomplete scaffold."
  log_error "This happens when python3-venv (or python3.X-venv) is not"
  log_error "installed on the system. Without this package, python3 -m venv"
  log_error "creates a partial venv without the activation scripts."
  log_error ""
  log_error "Fix with (Debian/Ubuntu):"
  log_error "  sudo apt update && sudo apt install -y python3-venv"
  log_error "  # or for a specific version:"
  log_error "  sudo apt install -y python3.11-venv"
  log_error ""
  log_error "Then rebuild the venv:"
  log_error "  ./scripts/setup.sh --recreate --bootstrap-pip --with-dev"
  exit 1
fi

# ----------------------------------------------------------------------
# Verifica / bootstrap di pip
# ----------------------------------------------------------------------

ensure_pip() {
  # If pip is available, do nothing.
  if "${VENV_PYTHON}" -m pip --version >/dev/null 2>&1; then
    return 0
  fi
  log_warn "pip not available in the venv. Trying to bootstrap..."
  # 1) Try ensurepip (works on recent Ubuntu/Debian)
  if "${VENV_PYTHON}" -m ensurepip --upgrade >/dev/null 2>&1; then
    log_ok "pip installed via ensurepip"
    return 0
  fi
  # 2) Try get-pip.py from PyPA (requires network + write access in /tmp)
  if command -v curl >/dev/null 2>&1; then
    local get_pip
    get_pip="$(mktemp -t get-pip-XXXXXX.py)"
    if curl -fsSL -o "${get_pip}" https://bootstrap.pypa.io/get-pip.py \
       && "${VENV_PYTHON}" "${get_pip}" >/dev/null 2>&1; then
      rm -f "${get_pip}"
      log_ok "pip installed via get-pip.py"
      return 0
    fi
    rm -f "${get_pip}"
  fi
  # 3) wget as a fallback
  if command -v wget >/dev/null 2>&1; then
    local get_pip
    get_pip="$(mktemp -t get-pip-XXXXXX.py)"
    if wget -q -O "${get_pip}" https://bootstrap.pypa.io/get-pip.py \
       && "${VENV_PYTHON}" "${get_pip}" >/dev/null 2>&1; then
      rm -f "${get_pip}"
      log_ok "pip installed via get-pip.py (wget)"
      return 0
    fi
    rm -f "${get_pip}"
  fi
  return 1
}

if [[ "${NO_PIP}" -eq 0 ]]; then
  if ! ensure_pip; then
    if [[ "${BOOTSTRAP_PIP}" -eq 1 ]]; then
      log_error "pip bootstrap failed. See the instructions above."
    else
      log_error "pip not available in the venv."
      log_error "Fix with: scripts/setup.sh --bootstrap-pip"
      log_error "or:        python3 -m ensurepip --upgrade  (with the venv active)"
      log_error "or:        curl -sSL https://bootstrap.pypa.io/get-pip.py | .venv/bin/python"
    fi
    exit 1
  fi
  log_step "Upgrading pip"
  "${VENV_PYTHON}" -m pip install --upgrade pip wheel setuptools >/dev/null
fi

log_step "Installing base dependencies"
"${VENV_PYTHON}" -m pip install -r "${PROJECT_ROOT}/requirements.txt"
"${VENV_PYTHON}" -m pip install --no-deps -e "${PROJECT_ROOT}"

if [[ "${WITH_DEV}" -eq 1 ]]; then
  log_step "Installing development dependencies"
  "${VENV_PYTHON}" -m pip install -r "${PROJECT_ROOT}/requirements-dev.txt"
fi

log_step "Verifying the installation"
"${VENV_PYTHON}" -c "import mcp, fastapi, uvicorn, pydantic; print('mcp, fastapi, uvicorn, pydantic imported')"
"${VENV_PYTHON}" -c "import wiki_core, mcp_server, mcp_server.http, rest_api; print('application modules OK')"

if [[ "${CONFIGURE}" -eq 1 ]]; then
  log_step "Configuring root, token and HTTPS interface"
  CONFIG_ARGS=()
  [[ -n "${CONFIG_ROOT}" ]] && CONFIG_ARGS+=(--root "${CONFIG_ROOT}")
  [[ -n "${CONFIG_TOKEN}" ]] && CONFIG_ARGS+=(--token "${CONFIG_TOKEN}")
  [[ -n "${CONFIG_HTTPS}" ]] && CONFIG_ARGS+=(--https "${CONFIG_HTTPS}")
  [[ -n "${CONFIG_HOST}" ]] && CONFIG_ARGS+=(--host "${CONFIG_HOST}")
  [[ -n "${CONFIG_PORT}" ]] && CONFIG_ARGS+=(--port "${CONFIG_PORT}")
  [[ -n "${CONFIG_URL}" ]] && CONFIG_ARGS+=(--url "${CONFIG_URL}")
  [[ -n "${CONFIG_CERT}" ]] && CONFIG_ARGS+=(--cert "${CONFIG_CERT}")
  [[ -n "${CONFIG_KEY}" ]] && CONFIG_ARGS+=(--key "${CONFIG_KEY}")
  if [[ -z "${CONFIG_HTTPS}" ]]; then
    CONFIG_ARGS+=(--no-apply)
  fi
  "${PROJECT_ROOT}/scripts/configure.sh" "${CONFIG_ARGS[@]}"
fi

log_ok "Setup completed."
log_info "Activate the venv with: source ${VENV_DIR}/bin/activate"
