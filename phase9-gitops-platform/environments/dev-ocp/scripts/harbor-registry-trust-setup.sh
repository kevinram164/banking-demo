#!/usr/bin/env bash
# Trust Harbor Route TLS trên OCP — fix:
#   x509: certificate signed by unknown authority
# khi kubelet pull harbor-platform.apps.ocp01.npd.co
#
#   ./environments/dev-ocp/scripts/harbor-registry-trust-setup.sh
#
# Nguồn CA (thứ tự):
#   1) Secret ESO harbor-registry-ca-vault (Vault secret/platform/harbor-registry-ca)
#   2) openshift-ingress-operator/router-ca
#   3) leaf cert từ HARBOR_HOST:443
#
# Lab: INSECURE=1 → insecureRegistries (không trust CA)
set -euo pipefail

HARBOR_HOST="${HARBOR_HOST:-harbor-platform.apps.ocp01.npd.co}"
CM_NAME="${CM_NAME:-harbor-registry-ca}"
ESO_SECRET="${ESO_SECRET:-harbor-registry-ca-vault}"
NS_CONFIG="openshift-config"
INSECURE="${INSECURE:-0}"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

if [[ "${INSECURE}" == "1" ]]; then
  echo "==> Lab: đánh dấu ${HARBOR_HOST} là insecureRegistries"
  EXISTING="$(oc get image.config.openshift.io/cluster -o jsonpath='{.spec.registrySources.insecureRegistries[*]}' 2>/dev/null || true)"
  if echo " ${EXISTING} " | grep -q " ${HARBOR_HOST} "; then
    echo "    đã có trong insecureRegistries"
  else
    oc patch image.config.openshift.io/cluster --type=merge -p="{
      \"spec\":{\"registrySources\":{\"insecureRegistries\":[\"${HARBOR_HOST}\"]}}
    }"
  fi
  echo "OK — đợi MCP/crio apply (có thể vài phút / reboot worker)."
  echo "  oc get mcp"
  exit 0
fi

CA_FILE="${TMP}/ca.crt"
if oc get secret "${ESO_SECRET}" -n "${NS_CONFIG}" &>/dev/null; then
  echo "==> CA từ ESO Secret ${ESO_SECRET} (Vault platform/harbor-registry-ca)"
  oc get secret "${ESO_SECRET}" -n "${NS_CONFIG}" -o jsonpath='{.data.ca\.crt}' | base64 -d > "${CA_FILE}"
  HOST_FROM_SECRET="$(oc get secret "${ESO_SECRET}" -n "${NS_CONFIG}" -o jsonpath='{.data.registry_host}' 2>/dev/null | base64 -d || true)"
  if [[ -n "${HOST_FROM_SECRET}" ]]; then
    HARBOR_HOST="${HOST_FROM_SECRET}"
  fi
elif oc get secret router-ca -n openshift-ingress-operator &>/dev/null; then
  echo "==> CA từ openshift-ingress-operator/router-ca (chưa có ESO Secret)"
  echo "    Seed Vault: ./vault-seed-harbor-registry-ca.sh"
  oc extract secret/router-ca -n openshift-ingress-operator --keys=tls.crt --to="${TMP}" --confirm
  mv "${TMP}/tls.crt" "${CA_FILE}"
else
  echo "==> WARN: lấy leaf cert từ ${HARBOR_HOST}:443"
  echo | openssl s_client -showcerts -servername "${HARBOR_HOST}" -connect "${HARBOR_HOST}:443" 2>/dev/null \
    | openssl x509 -outform PEM > "${CA_FILE}"
fi

if [[ ! -s "${CA_FILE}" ]]; then
  echo "ERROR: CA file trống"
  exit 1
fi

echo "==> ConfigMap ${CM_NAME} trong ${NS_CONFIG} (key = ${HARBOR_HOST})"
oc create configmap "${CM_NAME}" -n "${NS_CONFIG}" \
  --from-file="${HARBOR_HOST}=${CA_FILE}" \
  --dry-run=client -o yaml | oc apply -f -

echo "==> Patch image.config.openshift.io/cluster → additionalTrustedCA"
oc patch image.config.openshift.io/cluster --type=merge -p="{
  \"spec\":{\"additionalTrustedCA\":{\"name\":\"${CM_NAME}\"}}
}"

echo ""
echo "OK — CRI-O nhận CA mới (MCP có thể Updated=False vài phút)."
echo "  oc get image.config.openshift.io/cluster -o yaml | grep -A5 additionalTrustedCA"
echo "  oc get mcp"
echo "  oc delete pod -n banking --all --force --grace-period=0"
echo ""
echo "Lab nhanh: INSECURE=1 $0"
