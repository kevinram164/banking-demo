#!/usr/bin/env bash
# Harbor trên OCP: SA + SCC UID 999–10000, sync Helm để khôi phục runAsUser 10000
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> ServiceAccount harbor (ns platform)"
oc apply -f "${ROOT}/ocp-values/platform/harbor-serviceaccount.yaml"

echo "==> SCC harbor-uid-range"
oc apply -f "${ROOT}/ocp-values/scc/harbor-scc.yaml"

if ! oc get csidriver nfs.csi.k8s.io &>/dev/null; then
  echo ""
  echo "WARN: NFS CSI driver chưa có — Harbor PVC (jobservice/registry/db) sẽ FailedMount."
  echo "      Cài theo: phase9-gitops-platform/environments/dev-ocp/INSTALL-NFS-CSI.md"
  echo ""
fi

echo "==> Sync Harbor (ArgoCD) — khôi phục runAsUser 999/10000 từ Helm"
if command -v argocd &>/dev/null; then
  argocd app sync platform-harbor --force || true
else
  echo "    (argocd CLI không có — sync platform-harbor thủ công trên UI)"
fi

echo "==> Xóa pod Harbor cũ (SCC/UID cũ)"
oc delete pod -n platform -l app.kubernetes.io/instance=harbor --ignore-not-found
oc delete pod harbor-database-0 -n platform --ignore-not-found 2>/dev/null || true

echo ""
echo "Done. Kiểm tra:"
echo "  watch oc get pods -n platform -l app.kubernetes.io/instance=harbor"
echo "  oc logs -n platform deploy/harbor-jobservice --tail=20"
echo ""
echo "Nếu harbor-database-0 initdb Permission denied trên NFS:"
echo "  ./phase9-gitops-platform/environments/dev-ocp/scripts/harbor-reset-database-pvc.sh"
