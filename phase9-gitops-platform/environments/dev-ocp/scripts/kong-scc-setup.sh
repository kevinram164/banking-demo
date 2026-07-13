#!/usr/bin/env bash
# Kong trên OCP: chart cố định runAsUser 1000 — cần SCC kong-uid1000 (không anyuid cả ns).
#
#   ./environments/dev-ocp/scripts/kong-scc-setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS="${KONG_NS:-kong}"
SCC="kong-uid1000"
WAIT_SEC="${WAIT_SEC:-30}"

echo "==> Namespace ${NS}"
oc create ns "${NS}" --dry-run=client -o yaml | oc apply -f -

echo "==> Apply SCC ${SCC}"
oc apply -f "${ROOT}/ocp-values/scc/kong-scc.yaml"

# Discover SA từ Deployment kong-* (releaseName=kong → thường kong-kong)
SAS=()
elapsed=0
while [[ "${elapsed}" -lt "${WAIT_SEC}" ]]; do
  while IFS= read -r sa; do
    [[ -n "${sa}" ]] && SAS+=("${sa}")
  done < <(oc get deploy -n "${NS}" -o jsonpath='{range .items[*]}{.spec.template.spec.serviceAccountName}{"\n"}{end}' 2>/dev/null | sort -u || true)
  if [[ "${#SAS[@]}" -gt 0 ]]; then
    break
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done

if [[ "${#SAS[@]}" -eq 0 ]]; then
  echo "WARN: chưa có Deployment trong ${NS} — bind SA mặc định kong-kong"
  SAS=("kong-kong")
fi

for SA in "${SAS[@]}"; do
  [[ -z "${SA}" || "${SA}" == "default" ]] && SA="kong-kong"
  oc create serviceaccount "${SA}" -n "${NS}" --dry-run=client -o yaml | oc apply -f -
  echo "==> Bind SCC ${SCC} → SA ${SA}"
  oc adm policy add-scc-to-user "${SCC}" -z "${SA}" -n "${NS}"
done

# Jobs PreSync (wait/init) đôi khi dùng default SA
oc adm policy add-scc-to-user "${SCC}" -z default -n "${NS}" 2>/dev/null || true

if oc get deploy -n "${NS}" -l app.kubernetes.io/name=kong &>/dev/null; then
  echo "==> Rollout restart Kong"
  oc rollout restart deployment -n "${NS}" -l app.kubernetes.io/name=kong
  oc rollout status deployment -n "${NS}" -l app.kubernetes.io/name=kong --timeout=180s || true
fi

echo ""
echo "OK — kiểm tra:"
echo "  oc get pods -n ${NS}"
echo "  oc get events -n ${NS} --field-selector reason=FailedCreate --sort-by=.lastTimestamp | tail -5"
