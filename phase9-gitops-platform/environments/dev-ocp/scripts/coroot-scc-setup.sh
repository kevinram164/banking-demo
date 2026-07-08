#!/usr/bin/env bash
# Coroot Prometheus trên OCP: chart/operator chạy UID 65534 — cần SCC coroot-prometheus-65534
#
# Chạy sau khi sync observability-coroot-ce (hoặc trước — SA prometheus được tạo khi deploy):
#   ./environments/dev-ocp/scripts/coroot-scc-setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NS="${OBSERVABILITY_NS:-observability}"
SCC="coroot-prometheus-65534"

echo "==> Apply SCC ${SCC}"
oc apply -f "${ROOT}/ocp-values/scc/coroot-prometheus-scc.yaml"

echo "==> Đợi Deployment prometheus (nếu chưa có)"
for i in $(seq 1 30); do
  if oc get deploy prometheus -n "${NS}" &>/dev/null; then
    break
  fi
  sleep 5
done

SA="$(oc get deploy prometheus -n "${NS}" -o jsonpath='{.spec.template.spec.serviceAccountName}' 2>/dev/null || true)"
if [[ -z "${SA}" ]]; then
  SA="prometheus"
  echo "WARN: chưa thấy deploy/prometheus — dùng SA mặc định: ${SA}"
else
  echo "==> Prometheus SA: ${SA}"
fi

oc create serviceaccount "${SA}" -n "${NS}" --dry-run=client -o yaml | oc apply -f -

echo "==> Bind SCC → SA ${SA} (ns ${NS})"
oc adm policy add-scc-to-user "${SCC}" -z "${SA}" -n "${NS}"

# Cập nhật users[] trong SCC (idempotent)
oc patch scc "${SCC}" --type=json -p="[
  {\"op\":\"add\",\"path\":\"/users/-\",\"value\":\"system:serviceaccount:${NS}:${SA}\"}
]" 2>/dev/null || true

echo "==> Restart prometheus nếu đang FailedCreate"
if oc get deploy prometheus -n "${NS}" &>/dev/null; then
  oc rollout restart deploy/prometheus -n "${NS}" || true
fi

echo "OK — kiểm tra:"
echo "  oc get pods -n ${NS} -l app.kubernetes.io/name=prometheus"
echo "  oc get rs -n ${NS} | grep prometheus"
