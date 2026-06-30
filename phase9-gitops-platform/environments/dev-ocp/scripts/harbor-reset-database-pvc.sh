#!/usr/bin/env bash
# Lab: reset Harbor Postgres PVC khi initdb Permission denied trên NFS
set -euo pipefail

NS="${1:-platform}"
PVC="database-data-harbor-database-0"
WAIT="${WAIT_PVC_SECONDS:-60}"

echo "==> Scale harbor-database to 0"
oc scale statefulset harbor-database -n "${NS}" --replicas=0

echo "==> Xóa pod (nếu Terminating treo)"
oc delete pod harbor-database-0 -n "${NS}" --ignore-not-found --grace-period=0 --force 2>/dev/null || true

if oc get pod harbor-database-0 -n "${NS}" &>/dev/null; then
  echo "    Đợi pod xóa (tối đa ${WAIT}s)..."
  oc wait --for=delete "pod/harbor-database-0" -n "${NS}" --timeout="${WAIT}s" || {
    echo "WARN: pod vẫn còn — kiểm tra: oc get pod harbor-database-0 -n ${NS}"
  }
fi

echo "==> Delete PVC (không chờ CSI — tránh treo)"
oc delete pvc "${PVC}" -n "${NS}" --ignore-not-found --wait=false

if oc get pvc "${PVC}" -n "${NS}" &>/dev/null; then
  echo "    PVC đang Terminating — đợi tối đa ${WAIT}s..."
  for _ in $(seq 1 "${WAIT}"); do
    oc get pvc "${PVC}" -n "${NS}" &>/dev/null || break
    sleep 1
  done
fi

if oc get pvc "${PVC}" -n "${NS}" &>/dev/null; then
  echo ""
  echo "WARN: PVC vẫn Terminating. Chạy thủ công:"
  echo "  oc get pvc ${PVC} -n ${NS}"
  echo "  oc get pv | grep ${PVC}"
  echo "  # Trên NFS server:"
  echo "  rm -rf /shares/registry/${NS}/${PVC}"
  echo "  oc patch pv <pv-name> -p '{\"metadata\":{\"finalizers\":null}}' --type=merge"
  echo ""
fi

echo "==> Scale harbor-database to 1"
oc scale statefulset harbor-database -n "${NS}" --replicas=1

echo ""
echo "Done. Kiểm tra:"
echo "  oc get pvc,pod -n ${NS} | grep -E 'harbor-database|database-data'"
echo "  oc get pod harbor-database-0 -n ${NS} -o wide"
