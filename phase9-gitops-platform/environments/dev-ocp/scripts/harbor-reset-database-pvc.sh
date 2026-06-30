#!/usr/bin/env bash
# Lab: reset Harbor Postgres PVC khi initdb Permission denied trên NFS
# (PVC tạo lúc pod chạy UID sai → thư mục NFS không writable bởi UID 999)
set -euo pipefail

NS="${1:-platform}"

echo "==> Scale harbor-database to 0"
oc scale statefulset harbor-database -n "${NS}" --replicas=0
oc wait --for=delete pod/harbor-database-0 -n "${NS}" --timeout=120s 2>/dev/null || true

echo "==> Delete database PVC"
oc delete pvc database-data-harbor-database-0 -n "${NS}" --ignore-not-found

echo "==> (Tùy chọn) Xóa subdir trên NFS server nếu vẫn lỗi:"
echo "    rm -rf /shares/registry/${NS}/database-data-harbor-database-0"

echo "==> Scale harbor-database to 1"
oc scale statefulset harbor-database -n "${NS}" --replicas=1

echo ""
echo "Kiểm tra STS dùng UID 999 + SA harbor:"
echo "  oc get sts harbor-database -n ${NS} -o jsonpath='{.spec.template.spec.securityContext}{\"\\n\"}{.spec.template.spec.serviceAccountName}{\"\\n\"}'"
echo "  watch oc get pods -n ${NS} harbor-database-0"
