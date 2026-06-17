#!/usr/bin/env bash
# Mostra lo stato dei servizi wiki-kiss.
set -euo pipefail

_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${_LIB}/lib.sh"

usage() {
  cat <<EOF
${C_BOLD}Uso:${C_RESET} scripts/status.sh

Mostra lo stato corrente dei servizi (mcp, rest) leggendo i file pid
in var/run/.
EOF
}

if [[ $# -gt 0 ]]; then
  case "$1" in
    -h|--help) usage; exit 0 ;;
    *) log_error "Argomento sconosciuto: $1"; usage; exit 2 ;;
  esac
fi

ensure_dirs
load_env_file

printf "%s%sWiki KISS — stato servizi%s\n" "${C_BOLD}" "${C_CYAN}" "${C_RESET}"
printf "  project root: %s\n" "${PROJECT_ROOT}"
printf "  wiki root:    %s\n" "$(detect_wiki_root)"
printf "  venv:         %s\n" \
  "$( [[ -x "${VENV_PYTHON}" ]] && printf "%s" "${VENV_PYTHON}" || printf "(non trovato — esegui scripts/setup.sh)" )"
echo
print_status_line "mcp"      "Server MCP (stdio) per agenti AI locali"
print_status_line "mcp-http" "Server MCP Streamable HTTP (per client cloud)"
print_status_line "rest"     "API REST fallback (uvicorn)"
echo
if [[ -d "${LOG_DIR}" ]]; then
  printf "%sLog recenti:%s\n" "${C_BOLD}" "${C_RESET}"
  for f in "${LOG_DIR}"/*.log; do
    [[ -f "${f}" ]] || continue
    printf "  %s (%d righe)\n" "${f}" "$(wc -l <"${f}" | tr -d ' ')"
  done
fi
