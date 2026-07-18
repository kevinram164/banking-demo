#!/usr/bin/env bash
# Lab: mọi user OIDC đăng nhập ArgoCD = role:admin (không phụ thuộc group claim).
# Usage: ./argocd-rbac-oidc-admin-all.sh
set -euo pipefail
NS="${ARGOCD_NAMESPACE:-argocd}"

echo "==> Patch argocd-rbac-cm → policy.default=role:admin"
oc patch configmap argocd-rbac-cm -n "$NS" --type merge -p \
  '{"data":{"policy.default":"role:admin","scopes":"[groups, email]","policy.csv":"g, platform-admins, role:admin\ng, argocd-admins, role:admin\n"}}'

echo "==> Restart argocd-server"
oc rollout restart deployment/argocd-server -n "$NS"
oc rollout status deployment/argocd-server -n "$NS" --timeout=180s

echo "OK — logout ArgoCD, LOG IN VIA KEYCLOAK lại. Mọi user SSO đều admin."
