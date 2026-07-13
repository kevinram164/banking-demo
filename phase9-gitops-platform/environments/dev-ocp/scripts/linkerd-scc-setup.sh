#!/usr/bin/env bash
# Linkerd control-plane / viz trên OCP: UID cố định (2102/2103/65534) + NET_ADMIN/NET_RAW
# → cần privileged SCC (không fit restricted / nonroot).
#
#   ./environments/dev-ocp/scripts/linkerd-scc-setup.sh
#
# Lab: gán privileged cho mọi SA trong ns linkerd + linkerd-viz (giống OCP-DEPLOY-GUIDE).
set -euo pipefail

NAMESPACES=("linkerd" "linkerd-viz")

for NS in "${NAMESPACES[@]}"; do
  if ! oc get ns "${NS}" &>/dev/null; then
    echo "SKIP: namespace ${NS} chưa tồn tại — sync linkerd-crds / linkerd-viz trước"
    continue
  fi

  echo "==> Bind privileged SCC → group system:serviceaccounts:${NS}"
  oc adm policy add-scc-to-group privileged "system:serviceaccounts:${NS}"

  # Restart control-plane / viz nếu đã có
  if oc get deploy -n "${NS}" &>/dev/null; then
    echo "==> Rollout restart deployments in ${NS}"
    oc rollout restart deployment -n "${NS}" --all 2>/dev/null || true
  fi
done

echo ""
echo "OK — kiểm tra:"
echo "  oc get pods -n linkerd"
echo "  oc get pods -n linkerd-viz"
echo "  linkerd check || true"
echo ""
echo "Nếu banking pods (sidecar) vẫn Forbidden UID 2102:"
echo "  oc adm policy add-scc-to-group privileged system:serviceaccounts:banking"
echo "  (hoặc chỉ SA từng service — lab thường dùng group)"
