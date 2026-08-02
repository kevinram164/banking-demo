#!/usr/bin/env bash
# OpenSearch / Dashboards trên OCP: chart cố định runAsUser/fsGroup 1000.
#
#   ./environments/dev-ocp/scripts/opensearch-scc-setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS="${LOGGING_NS:-logging}"
SCC="opensearch-uid1000"

echo "==> Namespace ${NS}"
oc create ns "${NS}" --dry-run=client -o yaml | oc apply -f -

echo "==> Apply SCC ${SCC}"
oc apply -f "${ROOT}/ocp-values/scc/opensearch-scc.yaml"

for SA in default opensearch opensearch-dashboards; do
  oc create serviceaccount "${SA}" -n "${NS}" --dry-run=client -o yaml | oc apply -f -
  echo "==> Bind SCC ${SCC} → SA ${SA}"
  oc adm policy add-scc-to-user "${SCC}" -z "${SA}" -n "${NS}"
done

# Kick recreate pods bị FailedCreate
echo "==> Delete stuck pods (nếu có)"
oc -n "${NS}" delete pod -l app.kubernetes.io/name=opensearch --force --grace-period=0 2>/dev/null || true
oc -n "${NS}" delete pod -l app.kubernetes.io/name=opensearch-dashboards --force --grace-period=0 2>/dev/null || true
# StatefulSet / Deployment sẽ tạo lại
oc -n "${NS}" delete pod -l app=opensearch-dashboards --force --grace-period=0 2>/dev/null || true

echo ""
echo "OK — kiểm tra:"
echo "  oc -n ${NS} get pods,scc"
echo "  oc -n ${NS} get events --field-selector reason=FailedCreate --sort-by=.lastTimestamp | tail -5"
echo "  oc get scc ${SCC} -o yaml | grep system:serviceaccount:${NS}"
