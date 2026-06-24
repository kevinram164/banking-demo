#!/usr/bin/env bash
# Kiểm tra registries.yaml trên mọi node k3s (server/agent)
# Usage: ./verify-harbor-registry-k3d.sh
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-npd}"

all_nodes="$(docker ps --filter "label=k3d.cluster=${CLUSTER_NAME}" --format '{{.Names}}')"
if [[ -z "${all_nodes}" ]]; then
  echo "No k3d containers for cluster '${CLUSTER_NAME}'."
  exit 1
fi

found=0
for node in ${all_nodes}; do
  [[ "${node}" == *-tools ]] && continue
  if ! docker exec "${node}" test -f /etc/rancher/k3s/registries.yaml 2>/dev/null; then
    echo "MISSING: ${node} — không có /etc/rancher/k3s/registries.yaml"
    continue
  fi
  found=$((found + 1))
  echo "=== ${node} ==="
  docker exec "${node}" cat /etc/rancher/k3s/registries.yaml
  echo ""
done

if [[ ${found} -eq 0 ]]; then
  echo "Chưa có node nào có registries.yaml. Chạy: ./configure-harbor-registry-k3d.sh"
  exit 1
fi

echo "Harbor services (platform):"
kubectl get svc -n platform -l app=harbor 2>/dev/null || kubectl get svc -n platform | grep harbor || true
