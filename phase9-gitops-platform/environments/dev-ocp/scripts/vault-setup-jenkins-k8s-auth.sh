#!/usr/bin/env bash
# Bật Vault Kubernetes auth + role cho Jenkins agent (jenkins-kaniko).
# Pipeline đọc secret/platform/harbor và secret/platform/github — không Jenkins credential.
#
# Chạy trên bastion (đã oc/kubectl login):
#   export VAULT_TOKEN=root   # dev/lab — production dùng token có quyền policy write
#   ./environments/dev-ocp/scripts/vault-setup-jenkins-k8s-auth.sh
set -euo pipefail

if command -v oc >/dev/null 2>&1; then
  KCTL=oc
elif command -v kubectl >/dev/null 2>&1; then
  KCTL=kubectl
else
  echo "Cần oc hoặc kubectl trong PATH" >&2
  exit 1
fi

VAULT_NS="${VAULT_NS:-vault}"
PLATFORM_NS="${PLATFORM_NS:-platform}"
AGENT_SA="${JENKINS_AGENT_SA:-jenkins-kaniko}"
VAULT_ROLE="${VAULT_ROLE:-jenkins-kaniko}"
VAULT_TOKEN="${VAULT_TOKEN:-root}"
REVIEWER_SA="${VAULT_K8S_REVIEWER_SA:-vault-kubernetes-auth}"

echo "==> SA reviewer cho Vault TokenReview (nếu chưa có)"
${KCTL} create serviceaccount "${REVIEWER_SA}" -n "${VAULT_NS}" --dry-run=client -o yaml | ${KCTL} apply -f -
${KCTL} create clusterrolebinding "${REVIEWER_SA}-delegator" \
  --clusterrole=system:auth-delegator \
  --serviceaccount="${VAULT_NS}:${REVIEWER_SA}" \
  --dry-run=client -o yaml | ${KCTL} apply -f -

REVIEWER_JWT="$(${KCTL} create token "${REVIEWER_SA}" -n "${VAULT_NS}" --duration=8760h)"

echo "==> Enable Kubernetes auth + policy + role trong vault-0"
${KCTL} exec -n "${VAULT_NS}" vault-0 -- sh -c "
set -euo pipefail
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=${VAULT_TOKEN}

vault auth enable kubernetes 2>/dev/null || true

vault write auth/kubernetes/config \
  kubernetes_host='https://kubernetes.default.svc:443' \
  token_reviewer_jwt='${REVIEWER_JWT}' \
  kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt \
  disable_iss_validation=true \
  disable_local_ca_jwt=true

vault policy write jenkins-kaniko - <<'POLICY'
path \"secret/data/platform/harbor\" {
  capabilities = [\"read\"]
}
path \"secret/data/platform/github\" {
  capabilities = [\"read\"]
}
POLICY

vault write auth/kubernetes/role/${VAULT_ROLE} \
  bound_service_account_names=${AGENT_SA} \
  bound_service_account_namespaces=${PLATFORM_NS} \
  policies=jenkins-kaniko \
  ttl=1h

echo '==> Verify role + secrets exist'
vault read auth/kubernetes/role/${VAULT_ROLE}
vault kv get secret/platform/harbor >/dev/null && echo 'OK secret/platform/harbor' || echo 'MISSING secret/platform/harbor — seed trước khi chạy pipeline'
vault kv get secret/platform/github >/dev/null && echo 'OK secret/platform/github' || echo 'MISSING secret/platform/github — seed trước khi chạy pipeline'
"

echo "==> Xong. Kiểm tra login từ pod agent:"
cat <<EOF
  ${KCTL} run vault-test --rm -i --restart=Never -n ${PLATFORM_NS} \\
    --image=curlimages/curl --overrides='{"spec":{"serviceAccountName":"${AGENT_SA}"}}' -- \\
    sh -c 'JWT=\$(cat /var/run/secrets/kubernetes.io/serviceaccount/token); \\
      curl -sS --fail -X POST -d "{\\"jwt\\":\\"\$JWT\\",\\"role\\":\\"${VAULT_ROLE}\\"}" \\
      http://vault.${VAULT_NS}.svc.cluster.local:8200/v1/auth/kubernetes/login'
EOF
