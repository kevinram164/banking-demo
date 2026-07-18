#!/usr/bin/env bash
# ArgoCD: poll Git + auto-sync mỗi 5 phút (timeout.reconciliation).
# App cần syncPolicy.automated (phần lớn đã có trong GitOps).
# Usage: ./argocd-autosync-interval.sh [300s]
set -euo pipefail

NS="${ARGOCD_NAMESPACE:-argocd}"
INTERVAL="${1:-300s}"

echo "==> Patch argocd-cm timeout.reconciliation=${INTERVAL} (ns=${NS})"
oc patch configmap argocd-cm -n "$NS" --type merge \
  -p "{\"data\":{\"timeout.reconciliation\":\"${INTERVAL}\"}}"

echo "==> Restart application-controller để nhận interval mới"
if oc get statefulset argocd-application-controller -n "$NS" &>/dev/null; then
  oc rollout restart statefulset/argocd-application-controller -n "$NS"
  oc rollout status statefulset/argocd-application-controller -n "$NS" --timeout=180s
elif oc get deployment argocd-application-controller -n "$NS" &>/dev/null; then
  oc rollout restart deployment/argocd-application-controller -n "$NS"
  oc rollout status deployment/argocd-application-controller -n "$NS" --timeout=180s
else
  echo "WARN: không tìm thấy argocd-application-controller" >&2
fi

echo "==> Verify"
oc get configmap argocd-cm -n "$NS" -o jsonpath='{.data.timeout\.reconciliation}{"\n"}'
echo "OK: ArgoCD sẽ refresh Git ~ mỗi ${INTERVAL}; app có automated sẽ tự sync khi OutOfSync."
echo "Gợi ý (tùy chọn): GitHub webhook → sync ngay khi push, không chờ ${INTERVAL}."
