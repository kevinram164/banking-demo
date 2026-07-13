#!/usr/bin/env bash
# Seed Vault secret/platform/harbor-registry-ca từ OpenShift router-ca (lab).
# ESO → Secret harbor-registry-ca-vault (openshift-config).
# Sau đó: ./harbor-registry-trust-setup.sh  (ConfigMap + image.config)
#
#   export VAULT_ADDR=http://127.0.0.1:8200   # hoặc port-forward
#   export VAULT_TOKEN=root
#   ./environments/dev-ocp/scripts/vault-seed-harbor-registry-ca.sh
set -euo pipefail

HARBOR_HOST="${HARBOR_HOST:-harbor-platform.apps.ocp01.npd.co}"
VAULT_PATH="${VAULT_PATH:-secret/platform/harbor-registry-ca}"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

# Lab: nếu chưa export VAULT_TOKEN → lấy từ secret vault-token (ns external-secrets) hoặc default root
if [[ -z "${VAULT_TOKEN:-}" ]]; then
  if oc get secret vault-token -n external-secrets &>/dev/null; then
    VAULT_TOKEN="$(oc get secret vault-token -n external-secrets -o jsonpath='{.data.token}' | base64 -d)"
    echo "==> VAULT_TOKEN từ secret external-secrets/vault-token"
  else
    VAULT_TOKEN=root
    echo "==> VAULT_TOKEN chưa set — dùng lab default: root"
  fi
fi
export VAULT_TOKEN

VAULT_ADDR="${VAULT_ADDR:-http://vault.vault.svc.cluster.local:8200}"

echo "==> Lấy CA (router-ca hoặc leaf ${HARBOR_HOST})"
if oc get secret router-ca -n openshift-ingress-operator &>/dev/null; then
  oc extract secret/router-ca -n openshift-ingress-operator --keys=tls.crt --to="${TMP}" --confirm
  CA_FILE="${TMP}/tls.crt"
else
  echo | openssl s_client -showcerts -servername "${HARBOR_HOST}" -connect "${HARBOR_HOST}:443" 2>/dev/null \
    | openssl x509 -outform PEM > "${TMP}/harbor.crt"
  CA_FILE="${TMP}/harbor.crt"
fi

# Seed qua pod vault-0 nếu VAULT_ADDR nội bộ không reach từ bastion
# (không dùng oc cp — image Vault UBI thường không có tar)
if command -v vault &>/dev/null && curl -sf -o /dev/null --connect-timeout 2 "${VAULT_ADDR}/v1/sys/health" 2>/dev/null; then
  echo "==> vault kv put ${VAULT_PATH} (local vault CLI → ${VAULT_ADDR})"
  export VAULT_ADDR VAULT_TOKEN
  vault kv put "${VAULT_PATH}" \
    "ca.crt=@${CA_FILE}" \
    "registry_host=${HARBOR_HOST}"
else
  echo "==> vault CLI/addr không reach — seed qua oc exec -i vault-0 (stdin, không oc cp)"
  oc exec -i -n vault vault-0 -- sh -c "
    cat > /tmp/harbor-registry-ca.crt
    export VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN='${VAULT_TOKEN}'
    vault kv put ${VAULT_PATH} \
      ca.crt=@/tmp/harbor-registry-ca.crt \
      registry_host='${HARBOR_HOST}'
    rm -f /tmp/harbor-registry-ca.crt
  " < "${CA_FILE}"
fi

echo ""
echo "OK — Vault ${VAULT_PATH} seeded (registry_host=${HARBOR_HOST})"
echo "  Sync ArgoCD platform-external-secrets-config (hoặc đợi ESO refresh)"
echo "  oc get externalsecret harbor-registry-ca -n openshift-config"
echo "  oc get secret harbor-registry-ca-vault -n openshift-config"
echo "  ./phase9-gitops-platform/environments/dev-ocp/scripts/harbor-registry-trust-setup.sh"
