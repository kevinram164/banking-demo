#!/usr/bin/env bash
# Wrapper — chuyển sang namespace-scc-setup.sh (hướng chính)
exec "$(dirname "$0")/namespace-scc-setup.sh" "${1:-argocd}" "${@:2}"
