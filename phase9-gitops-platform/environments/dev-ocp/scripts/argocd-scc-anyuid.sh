#!/usr/bin/env bash
# DEPRECATED — dùng namespace-scc-setup.sh (SCC nonroot + UID range namespace)
# Giữ lại chỉ cho PoC nhanh khi chưa kịp patch UID.
set -euo pipefail
NS="${1:-argocd}"
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "WARNING: anyuid/privileged cả namespace — không khuyến nghị production."
echo "Khuyến nghị: $ROOT/namespace-scc-setup.sh $NS"
if [[ -t 0 ]]; then
  read -r -p "Tiếp tục gán anyuid? [y/N] " ans
  [[ "${ans,,}" == "y" ]] || exit 0
else
  echo "Non-interactive — thoát. Dùng namespace-scc-setup.sh"
  exit 1
fi

oc adm policy add-scc-to-group anyuid "system:serviceaccounts:${NS}"
oc adm policy add-scc-to-group privileged "system:serviceaccounts:${NS}"
oc rollout restart statefulset,deployment,daemonset -n "$NS" 2>/dev/null || true
echo "Done (lab only)."
