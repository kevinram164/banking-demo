#!/usr/bin/env bash
# Coroot Prometheus trên OCP: operator deploy coroot-prometheus với UID 65534
#
#   ./environments/dev-ocp/scripts/coroot-scc-setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NS="${OBSERVABILITY_NS:-observability}"
SCC="coroot-prometheus-65534"
WAIT_SEC="${WAIT_SEC:-30}"

echo "==> Namespace ${NS}"
oc create ns "${NS}" --dry-run=client -o yaml | oc apply -f -

echo "==> Apply SCC ${SCC}"
oc apply -f "${ROOT}/ocp-values/scc/coroot-prometheus-scc.yaml"

DEPLOY=""
SA=""
echo "==> Tìm Deployment *prometheus* (tối đa ${WAIT_SEC}s)"
elapsed=0
while [[ "${elapsed}" -lt "${WAIT_SEC}" ]]; do
  DEPLOY="$(oc get deploy -n "${NS}" -o name 2>/dev/null | grep -i prometheus | head -1 | sed 's|deployment.apps/||' || true)"
  if [[ -n "${DEPLOY}" ]]; then
    SA="$(oc get deploy "${DEPLOY}" -n "${NS}" -o jsonpath='{.spec.template.spec.serviceAccountName}' 2>/dev/null || true)"
    [[ -z "${SA}" ]] && SA="default"
    echo "    deploy/${DEPLOY} — SA: ${SA}"
    break
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done

if [[ -z "${DEPLOY}" ]]; then
  echo "WARN: chưa có Deployment *prometheus* — bind SCC cho SA mặc định coroot-prometheus"
  SA="coroot-prometheus"
  DEPLOY="coroot-prometheus"
fi

oc create serviceaccount "${SA}" -n "${NS}" --dry-run=client -o yaml | oc apply -f -

echo "==> Bind SCC → SA ${SA} (ns ${NS})"
oc adm policy add-scc-to-user "${SCC}" -z "${SA}" -n "${NS}"

if oc get deploy "${DEPLOY}" -n "${NS}" &>/dev/null; then
  echo "==> Rollout restart deploy/${DEPLOY}"
  oc rollout restart "deploy/${DEPLOY}" -n "${NS}"
  oc rollout status "deploy/${DEPLOY}" -n "${NS}" --timeout=120s || true
else
  echo "==> Chưa có deploy — sau khi ArgoCD sync coroot-ce, chạy lại script"
fi

echo ""
echo "OK — kiểm tra:"
echo "  oc get deploy,rs,pods -n ${NS} | grep -i prometheus"
echo "  oc describe rs -n ${NS} | grep -A3 'FailedCreate\\|runAsUser' || true"
