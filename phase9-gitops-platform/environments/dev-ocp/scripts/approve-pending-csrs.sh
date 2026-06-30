#!/usr/bin/env bash
# UPI/bare metal: approve CSR Pending (kubelet-serving) — sửa oc logs / tls: internal error
# Chạy định kỳ (cron 30m) hoặc sau khi thêm worker.
set -euo pipefail

PENDING=$(oc get csr -o jsonpath='{range .items[?(@.status.conditions==null)]}{.metadata.name}{"\n"}{end}' 2>/dev/null || true)

if [[ -z "${PENDING// }" ]]; then
  echo "No pending CSRs."
  exit 0
fi

echo "==> Approving pending CSRs:"
echo "$PENDING" | while read -r name; do
  [[ -z "$name" ]] && continue
  user=$(oc get csr "$name" -o jsonpath='{.spec.username}' 2>/dev/null || echo "?")
  echo "  $name ($user)"
  oc adm certificate approve "$name"
done

echo ""
echo "Done. Verify: oc get csr | grep Pending"
