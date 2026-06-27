#!/usr/bin/env bash
# KHẨN CẤP: bootstrap identity secret/configmap khi Helm còn externalCA:true.
# Với externalCA:false (mặc định hiện tại) → dùng reset-linkerd-control-plane-k3d.sh + ArgoCD Sync thay vì script này.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${SCRIPT_DIR}/../manifests/linkerd-identity-k3d/certs"

need_gen=false
for f in ca.crt issuer.crt issuer.key; do
  [[ -f "${CERT_DIR}/${f}" ]] || need_gen=true
done

if $need_gen; then
  echo "Thiếu file trong ${CERT_DIR}/ — tạo bằng gen-k3d-lab-certs.py ..."
  if ! python3 "${SCRIPT_DIR}/gen-k3d-lab-certs.py" 2>/dev/null; then
    python "${SCRIPT_DIR}/gen-k3d-lab-certs.py"
  fi
fi

for f in ca.crt issuer.crt issuer.key; do
  [[ -f "${CERT_DIR}/${f}" ]] || { echo "Vẫn thiếu ${CERT_DIR}/${f}. Cài: pip install cryptography"; exit 1; }
done

kubectl create namespace linkerd --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -k "${SCRIPT_DIR}/../manifests/linkerd-identity-k3d/"

echo "OK: linkerd-identity-trust-roots + linkerd-identity-issuer (kubernetes.io/tls)"
