#!/usr/bin/env bash
# OpenSearch / Dashboards OCP SCC — chạy lại nếu vẫn FailedCreate UID 1000
#
#   bash phase9-gitops-platform/environments/dev-ocp/scripts/opensearch-scc-setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS="${LOGGING_NS:-logging}"
SCC="opensearch-uid1000"

echo "==> Namespace ${NS}"
oc create ns "${NS}" --dry-run=client -o yaml | oc apply -f -

echo "==> Apply SCC ${SCC}"
oc apply -f "${ROOT}/ocp-values/scc/opensearch-scc.yaml"

# Mọi SA có thể chạy pod trong ns (STS thường default hoặc opensearch)
mapfile -t SAS < <(oc get sa -n "${NS}" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null || true)
SAS+=(default opensearch opensearch-dashboards)
# unique
readarray -t SAS < <(printf '%s\n' "${SAS[@]}" | sort -u)

for SA in "${SAS[@]}"; do
  [[ -z "${SA}" ]] && continue
  oc create serviceaccount "${SA}" -n "${NS}" --dry-run=client -o yaml | oc apply -f -
  echo "==> Bind ${SCC} → ${SA}"
  oc adm policy add-scc-to-user "${SCC}" -z "${SA}" -n "${NS}"
done

# Lab fallback nếu custom SCC vẫn không match
echo "==> Fallback: bind anyuid cho default + opensearch*"
oc adm policy add-scc-to-user anyuid -z default -n "${NS}" || true
oc adm policy add-scc-to-user anyuid -z opensearch -n "${NS}" || true
oc adm policy add-scc-to-user anyuid -z opensearch-dashboards -n "${NS}" || true

echo "==> SA đang dùng bởi STS/Deploy:"
oc -n "${NS}" get sts,deploy -o custom-columns=KIND:.kind,NAME:.metadata.name,SA:.spec.template.spec.serviceAccountName 2>/dev/null || true

echo "==> SCC users (phải có system:serviceaccount:${NS}:...):"
oc get scc "${SCC}" -o jsonpath='{.users}' ; echo
oc get scc anyuid -o jsonpath='{.users}' 2>/dev/null | tr ' ' '\n' | grep "${NS}" || true

echo "==> Delete pods để recreate"
oc -n "${NS}" delete pod --all --force --grace-period=0 2>/dev/null || true

sleep 3
oc -n "${NS}" get pods
echo ""
echo "Nếu vẫn FailedCreate:"
echo "  oc -n ${NS} get sts npd-logs-master -o yaml | grep -A2 serviceAccount"
echo "  oc get scc ${SCC} -o yaml | grep -A20 users"
