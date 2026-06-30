#!/usr/bin/env bash
# Harbor trên OCP: SA + SCC UID 999–10000, sync Helm để khôi phục runAsUser 10000
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> ServiceAccount harbor (ns platform)"
oc apply -f "${ROOT}/ocp-values/platform/harbor-serviceaccount.yaml"

echo "==> SCC harbor-uid-range"
oc apply -f "${ROOT}/ocp-values/scc/harbor-scc.yaml"

echo "==> Sync Harbor (ArgoCD) — khôi phục securityContext runAsUser 10000 từ Helm"
if command -v argocd &>/dev/null; then
  argocd app sync platform-harbor --force || true
else
  echo "    (argocd CLI không có — sync platform-harbor thủ công trên UI)"
fi

echo "==> Restart Harbor workloads"
oc rollout restart deployment,statefulset -n platform -l app.kubernetes.io/instance=harbor 2>/dev/null || \
  oc rollout restart deployment,statefulset -n platform 2>/dev/null || true

echo ""
echo "Done. Kiểm tra:"
echo "  watch oc get pods -n platform -l app.kubernetes.io/instance=harbor"
echo "  oc logs -n platform deploy/harbor-jobservice --tail=20"
