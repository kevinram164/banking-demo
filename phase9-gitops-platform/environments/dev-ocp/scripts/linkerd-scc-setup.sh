#!/usr/bin/env bash
# Linkerd trên OCP: UID cố định (2102/2103/65534) + NET_ADMIN/NET_RAW
# → cần privileged SCC (không fit restricted / nonroot).
#
# Áp dụng cho:
#   - linkerd / linkerd-viz (control-plane + Viz)
#   - npd-banking (workload có sidecar: linkerd-init UID 0 + proxy UID 2102)
#
# Triệu chứng:
#   - linkerd-destination / metrics-api: UID 2102/2103 Forbidden
#   - npd-banking ReplicaSet: initContainers runAsUser 0 + NET_ADMIN Forbidden
#
#   ./environments/dev-ocp/scripts/linkerd-scc-setup.sh
#   ./environments/dev-ocp/scripts/linkerd-scc-setup.sh npd-banking   # chỉ ns npd-banking
set -euo pipefail

if [[ $# -gt 0 ]]; then
  NAMESPACES=("$@")
else
  NAMESPACES=("linkerd" "linkerd-viz" "npd-banking")
fi

for NS in "${NAMESPACES[@]}"; do
  if ! oc get ns "${NS}" &>/dev/null; then
    echo "SKIP: namespace ${NS} chưa tồn tại"
    continue
  fi

  echo "==> Bind privileged SCC → group system:serviceaccounts:${NS}"
  oc adm policy add-scc-to-group privileged "system:serviceaccounts:${NS}"

  # Bind từng SA (phòng khi group binding chưa áp dụng ngay cho SA mới)
  while IFS= read -r sa; do
    [[ -z "${sa}" ]] && continue
    echo "    SA ${sa}"
    oc adm policy add-scc-to-user privileged -z "${sa}" -n "${NS}" 2>/dev/null || true
  done < <(oc get sa -n "${NS}" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null || true)

  if oc get deploy -n "${NS}" --no-headers 2>/dev/null | grep -q .; then
    echo "==> Rollout restart deployments in ${NS}"
    oc rollout restart deployment -n "${NS}" --all 2>/dev/null || true
  fi
done

echo ""
echo "OK — kiểm tra:"
echo "  oc get pods -n linkerd"
echo "  oc get pods -n linkerd-viz"
echo "  oc get pods -n npd-banking"
echo "  linkerd check || true"
echo ""
echo "LƯU Ý: đừng chạy namespace-scc-setup.sh npd-banking sau bước này"
echo "  (script đó gỡ privileged + gán nonroot → mesh sidecar lại Forbidden)."
