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
#   5. Client scopes → Dedicated → Configure a new mapper → Group Membership → claim: groups
#   6. Group: platform-admins + gán user test
#   7. Copy Client secret
#
# Usage:
#   export ARGOCD_OIDC_CLIENT_SECRET='...'
#   ./argocd-oidc-keycloak.sh
#
# Lab TLS (Route OCP self-signed / private CA):
#   Mặc định gắn rootCA từ OpenShift ingress CA.
#   Nếu vẫn lỗi x509: export OIDC_TLS_INSECURE=true  (skip verify — chỉ lab)
#
# Env tùy chọn:
#   ARGOCD_NAMESPACE=argocd
#   ARGOCD_URL=https://argocd-server-argocd.apps.ocp01.npd.co
#   KEYCLOAK_ISSUER=https://keycloak-platform.apps.ocp01.npd.co/realms/platform
#   OIDC_CLIENT_ID=argocd
#   OIDC_TLS_INSECURE=true|false
set -euo pipefail

NS="${ARGOCD_NAMESPACE:-argocd}"
ARGOCD_URL="${ARGOCD_URL:-https://argocd-server-argocd.apps.ocp01.npd.co}"
ISSUER="${KEYCLOAK_ISSUER:-https://keycloak-platform.apps.ocp01.npd.co/realms/platform}"
CLIENT_ID="${OIDC_CLIENT_ID:-argocd}"
SECRET="${ARGOCD_OIDC_CLIENT_SECRET:-}"
OIDC_TLS_INSECURE="${OIDC_TLS_INSECURE:-false}"

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
echo "    TLS insecure skip: ${OIDC_TLS_INSECURE}"

echo "==> Patch secret/argocd-secret (oidc.keycloak.clientSecret)"
oc patch secret argocd-secret -n "$NS" --type merge -p \
  "{\"stringData\":{\"oidc.keycloak.clientSecret\":\"${SECRET}\"}}"

# Lấy CA Route/Ingress OCP (tránh x509 unknown authority)
ROOT_CA=""
if [[ "${OIDC_TLS_INSECURE}" != "true" ]]; then
  echo "==> Fetch OpenShift ingress / router CA for oidc rootCA"
  ROOT_CA=$(oc get configmap default-ingress-cert -n openshift-config-managed \
    -o jsonpath='{.data.ca-bundle\.crt}' 2>/dev/null || true)
  if [[ -z "$ROOT_CA" ]]; then
    ROOT_CA=$(oc get secret router-ca -n openshift-ingress-operator \
      -o jsonpath='{.data.tls\.crt}' 2>/dev/null | base64 -d 2>/dev/null || true)
  fi
  if [[ -z "$ROOT_CA" ]]; then
    echo "WARN: không lấy được ingress CA — sẽ set oidc.tls.insecure.skip.verify=true (lab)" >&2
    OIDC_TLS_INSECURE=true
  fi
fi

OIDC_PATCH=$(
  ARGOCD_URL="$ARGOCD_URL" CLIENT_ID="$CLIENT_ID" ISSUER="$ISSUER" \
  ROOT_CA="$ROOT_CA" OIDC_TLS_INSECURE="$OIDC_TLS_INSECURE" python3 - <<'PY'
import json, os, textwrap
url = os.environ["ARGOCD_URL"]
client_id = os.environ["CLIENT_ID"]
issuer = os.environ["ISSUER"]
root_ca = os.environ.get("ROOT_CA", "").strip()
insecure = os.environ.get("OIDC_TLS_INSECURE", "false").lower() == "true"

lines = [
    "name: Keycloak",
    f"issuer: {issuer}",
    f"clientID: {client_id}",
    "clientSecret: $oidc.keycloak.clientSecret",
    "requestedScopes:",
    "  - openid",
    "  - profile",
    "  - email",
    # Không request scope "groups" — Keycloak không có client scope đó → invalid_scope.
    # Claim groups vẫn có nhờ mapper Group Membership trên argocd-dedicated.
    (
        f"logoutURL: {issuer}/protocol/openid-connect/logout"
        f"?client_id={client_id}&post_logout_redirect_uri={{{{logoutRedirectURL}}}}"
    ),
]
if root_ca and not insecure:
    lines.append("rootCA: |")
    for line in root_ca.splitlines():
        lines.append(f"  {line}")

data = {"url": url, "oidc.config": "\n".join(lines) + "\n"}
if insecure:
    data["oidc.tls.insecure.skip.verify"] = "true"
print(json.dumps({"data": data}))
PY
)

echo "==> Patch configmap/argocd-cm (url + oidc.config + TLS)"
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
echo "OK — mở ${ARGOCD_URL} → LOG IN VIA KEYCLOAK"
echo "Group platform-admins → role:admin. Local admin vẫn dùng được."
