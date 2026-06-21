#!/usr/bin/env bash
# Tạo trust anchor + issuer cho Linkerd (lab k3d). Chạy một lần trước sync linkerd-control-plane.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${SCRIPT_DIR}/../certs"
mkdir -p "$CERT_DIR"

if command -v step >/dev/null 2>&1; then
  step certificate create root.linkerd.cluster.local \
    "$CERT_DIR/ca.crt" "$CERT_DIR/ca.key" \
    --profile root-ca --no-password --insecure --not-after=87600h

  step certificate create identity.linkerd.cluster.local \
    "$CERT_DIR/issuer.crt" "$CERT_DIR/issuer.key" \
    --profile intermediate-ca --not-after=87600h \
    --ca "$CERT_DIR/ca.crt" --ca-key "$CERT_DIR/ca.key" \
    --no-password --insecure
else
  echo "Cài step-cli: https://smallstep.com/docs/step-cli/ (hoặc apt install step-cli)"
  exit 1
fi

# Secret cho kubectl apply (tùy chọn)
kubectl create namespace linkerd --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap linkerd-identity-trust-roots \
  -n linkerd \
  --from-file=ca.crt="$CERT_DIR/ca.crt" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic linkerd-identity-issuer \
  -n linkerd \
  --from-file=tls.crt="$CERT_DIR/issuer.crt" \
  --from-file=tls.key="$CERT_DIR/issuer.key" \
  --dry-run=client -o yaml | kubectl apply -f -

# Helm values snippet (ArgoCD inline values có thể copy từ đây)
cat > "$CERT_DIR/linkerd-identity.yaml" <<EOF
# Merge vào linkerd-control-plane helm values (LAB ONLY — không commit private key lên Git public)
identityTrustAnchorsPEM: |
$(sed 's/^/  /' "$CERT_DIR/ca.crt")
identity:
  issuer:
    tls:
      crtPEM: |
$(sed 's/^/        /' "$CERT_DIR/issuer.crt")
      keyPEM: |
$(sed 's/^/        /' "$CERT_DIR/issuer.key")
EOF

echo "OK: $CERT_DIR/linkerd-identity.yaml"
echo "Secret linkerd-identity-issuer trong ns linkerd đã apply."
