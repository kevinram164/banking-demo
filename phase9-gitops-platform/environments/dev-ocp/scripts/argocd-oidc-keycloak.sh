#!/usr/bin/env bash
# Phase 2 — ArgoCD OIDC → Keycloak (realm platform, client argocd)
#
# Trước khi chạy (Keycloak Admin):
#   1. Realm: platform
#   2. Client ID: argocd (confidential, Standard flow ON)
#   3. Valid redirect URIs:
#        https://argocd-server-argocd.apps.ocp01.npd.co/auth/callback
#   4. Web origins:
#        https://argocd-server-argocd.apps.ocp01.npd.co
#   5. Client scopes → Dedicated mapper "Group Membership" → claim: groups
#   6. Group: platform-admins + gán user test
#   7. Copy Client secret
#
# Usage:
#   export ARGOCD_OIDC_CLIENT_SECRET='...'
#   ./argocd-oidc-keycloak.sh
#
# Env tùy chọn:
#   ARGOCD_NAMESPACE=argocd
#   ARGOCD_URL=https://argocd-server-argocd.apps.ocp01.npd.co
#   KEYCLOAK_ISSUER=https://keycloak-platform.apps.ocp01.npd.co/realms/platform
#   OIDC_CLIENT_ID=argocd
set -euo pipefail

NS="${ARGOCD_NAMESPACE:-argocd}"
ARGOCD_URL="${ARGOCD_URL:-https://argocd-server-argocd.apps.ocp01.npd.co}"
ISSUER="${KEYCLOAK_ISSUER:-https://keycloak-platform.apps.ocp01.npd.co/realms/platform}"
CLIENT_ID="${OIDC_CLIENT_ID:-argocd}"
SECRET="${ARGOCD_OIDC_CLIENT_SECRET:-}"

if [[ -z "$SECRET" ]]; then
  echo "ERROR: set ARGOCD_OIDC_CLIENT_SECRET (Keycloak client secret for '${CLIENT_ID}')" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 required to build JSON patch" >&2
  exit 1
fi

echo "==> ns=${NS}"
echo "    ArgoCD URL: ${ARGOCD_URL}"
echo "    Issuer:     ${ISSUER}"
echo "    Client ID:  ${CLIENT_ID}"

echo "==> Patch secret/argocd-secret (oidc.keycloak.clientSecret)"
oc patch secret argocd-secret -n "$NS" --type merge -p \
  "{\"stringData\":{\"oidc.keycloak.clientSecret\":\"${SECRET}\"}}"

OIDC_PATCH=$(
  ARGOCD_URL="$ARGOCD_URL" CLIENT_ID="$CLIENT_ID" ISSUER="$ISSUER" python3 - <<'PY'
import json, os
url = os.environ["ARGOCD_URL"]
client_id = os.environ["CLIENT_ID"]
issuer = os.environ["ISSUER"]
cfg = "\n".join([
    "name: Keycloak",
    f"issuer: {issuer}",
    f"clientID: {client_id}",
    "clientSecret: $oidc.keycloak.clientSecret",
    "requestedScopes:",
    "  - openid",
    "  - profile",
    "  - email",
    "  - groups",
    (
        f"logoutURL: {issuer}/protocol/openid-connect/logout"
        f"?client_id={client_id}&post_logout_redirect_uri={{{{logoutRedirectURL}}}}"
    ),
])
print(json.dumps({"data": {"url": url, "oidc.config": cfg}}))
PY
)

echo "==> Patch configmap/argocd-cm (url + oidc.config)"
oc patch configmap argocd-cm -n "$NS" --type merge -p "$OIDC_PATCH"

RBAC_PATCH=$(python3 - <<'PY'
import json
policy = "g, platform-admins, role:admin\ng, argocd-admins, role:admin\n"
print(json.dumps({
    "data": {
        "policy.csv": policy,
        "policy.default": "role:readonly",
        "scopes": "[groups, email]",
    }
}))
PY
)

echo "==> Patch configmap/argocd-rbac-cm"
oc patch configmap argocd-rbac-cm -n "$NS" --type merge -p "$RBAC_PATCH"

echo "==> Restart argocd-server"
oc rollout restart deployment/argocd-server -n "$NS"
oc rollout status deployment/argocd-server -n "$NS" --timeout=180s

echo
echo "OK — mở ${ARGOCD_URL} → LOG IN VIA OIDC / KEYCLOAK"
echo "Group Keycloak platform-admins → ArgoCD role:admin; user khác → readonly."
echo "Local admin (argocd-initial-admin-secret) vẫn dùng được."
