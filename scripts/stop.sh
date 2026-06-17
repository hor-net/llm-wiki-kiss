#!/usr/bin/env bash
# Ferma uno o più servizi (mcp, rest, all).
set -euo pipefail

_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${_LIB}/lib.sh"

usage() {
  cat <<EOF
${C_BOLD}Uso:${C_RESET} scripts/stop.sh [servizio]

Servizi disponibili:
  mcp     Ferma il server MCP
  rest    Ferma l'API REST
  all     Ferma tutti i servizi (default)
EOF
}

target="${1:-all}"
case "${target}" in
  mcp)  stop_service mcp ;;
  rest) stop_service rest ;;
  all)  stop_service mcp || true
        stop_service rest || true ;;
  -h|--help) usage; exit 0 ;;
  *) log_error "Servizio sconosciuto: ${target}"; usage; exit 2 ;;
esac
