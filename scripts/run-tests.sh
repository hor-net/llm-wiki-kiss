#!/usr/bin/env bash
# Esegue la suite di test pytest.
set -euo pipefail

_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${_LIB}/lib.sh"

usage() {
  cat <<EOF
${C_BOLD}Uso:${C_RESET} scripts/run-tests.sh [opzioni-pytest...]

Esegue i test del progetto (pytest). Tutti gli argomenti sono passati
direttamente a pytest.

Esempio:
  scripts/run-tests.sh -q
  scripts/run-tests.sh tests/test_storage.py -k search
  scripts/run-tests.sh -q --maxfail=1
EOF
}

require_venv
cd "${PROJECT_ROOT}"
exec "${VENV_PYTHON}" -m pytest "$@"
