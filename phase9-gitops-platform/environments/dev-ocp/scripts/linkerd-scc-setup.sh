#!/usr/bin/env bash
# Linkerd control-plane / viz trên OCP: UID cố định (2102/2103/65534) + NET_ADMIN/NET_RAW
# → cần privileged SCC (không fit restricted / nonroot).
#
# Triệu chứng thường gặp:
#   - linkerd-destination: UID 2102 / NET_ADMIN Forbidden
#   - metrics-api / tap / web (linkerd-viz): UID 2103 Forbidden
#
#   ./environments/dev-ocp/scripts/linkerd-scc-setup.sh
set -euo pipefail

NAMESPACES=("linkerd" "linkerd-viz")

for NS in "${NAMESPACES[@]}"; do
  if ! oc get ns "${NS}" &>/dev/null; then
    echo "SKIP: namespace ${NS} chưa tồn tại — sync linkerd-crds / linkerd-viz trước"
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
echo "  oc get pods -n linkerd-viz | grep metrics-api"
echo "  linkerd check || true"
echo ""
echo "Nếu banking pods (sidecar) vẫn Forbidden UID 2102:"
echo "  oc adm policy add-scc-to-group privileged system:serviceaccounts:banking"
