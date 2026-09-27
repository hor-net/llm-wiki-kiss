#!/usr/bin/env bash
# Accesso locale offline al wiki tramite CLI.
set -euo pipefail

_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${_LIB}/lib.sh"

load_env_file
require_venv
exec "${VENV_PYTHON}" -m wiki_core.cli "$@"
