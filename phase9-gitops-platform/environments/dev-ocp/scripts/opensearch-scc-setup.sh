#!/usr/bin/env bash
# OpenSearch + Dashboards SCC — bind CẢ group SA ns logging
#
#   bash phase9-gitops-platform/environments/dev-ocp/scripts/opensearch-scc-setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS="${LOGGING_NS:-logging}"
SCC="opensearch-uid1000"

echo "==> Namespace ${NS}"
oc create ns "${NS}" --dry-run=client -o yaml | oc apply -f -

echo "==> Apply SCC ${SCC} (groups: system:serviceaccounts:${NS})"
oc apply -f "${ROOT}/ocp-values/scc/opensearch-scc.yaml"

# Group bind — phủ default + mọi SA chart tạo sau
echo "==> add-scc-to-group ${SCC} → system:serviceaccounts:${NS}"
oc adm policy add-scc-to-group "${SCC}" "system:serviceaccounts:${NS}"

# Lab: anyuid cho cả ns (Dashboards hay sót SA)
echo "==> add-scc-to-group anyuid → system:serviceaccounts:${NS}"
oc adm policy add-scc-to-group anyuid "system:serviceaccounts:${NS}"

echo "==> SAs + Deploy/STS SA names:"
oc -n "${NS}" get sa
oc -n "${NS}" get sts,deploy -o custom-columns=KIND:.kind,NAME:.metadata.name,SA:.spec.template.spec.serviceAccountName 2>/dev/null || true

echo "==> Verify groups on SCC:"
oc get scc "${SCC}" -o jsonpath='{.groups}' ; echo

echo "==> Restart dashboards + opensearch pods"
oc -n "${NS}" delete pod -l app.kubernetes.io/name=opensearch-dashboards --force --grace-period=0 2>/dev/null || true
oc -n "${NS}" delete pod -l app=opensearch-dashboards --force --grace-period=0 2>/dev/null || true
oc -n "${NS}" delete pod --selector=app.kubernetes.io/component=opensearch-dashboards --force --grace-period=0 2>/dev/null || true
# delete tất cả pod dashboards theo tên deploy
oc -n "${NS}" delete pod -l app.kubernetes.io/instance=opensearch-dashboards --force --grace-period=0 2>/dev/null || true
oc -n "${NS}" get deploy -o name 2>/dev/null | while read -r d; do
  oc -n "${NS}" rollout restart "$d" 2>/dev/null || true
done

sleep 2
oc -n "${NS}" get pods
echo ""
echo "OK nếu dashboards Running. Kiểm tra:"
echo "  oc -n ${NS} get pods"
echo "  oc get scc ${SCC} -o yaml | grep -A5 groups"
