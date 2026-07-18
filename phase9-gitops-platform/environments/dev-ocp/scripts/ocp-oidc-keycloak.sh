#!/usr/bin/env bash
# OpenShift cluster OAuth → Keycloak OpenID (Phase 4)
#
# Keycloak trước:
#   Client ID: ocp-console (confidential)
#   Redirect: https://oauth-openshift.apps.ocp01.npd.co/oauth2callback/keycloak
#   (đuôi /keycloak = identityProviders[].name bên dưới)
#
# Usage:
#   export OCP_OIDC_CLIENT_SECRET='...'
#   ./ocp-oidc-keycloak.sh
#
# Sau login SSO: user OCP mới chỉ là authenticated — gán role riêng:
#   oc adm policy add-cluster-role-to-user cluster-admin kiet.tran
#   (hoặc RoleBinding theo group nếu đã map claims.groups)
set -euo pipefail

ISSUER="${KEYCLOAK_ISSUER:-https://keycloak-platform.apps.ocp01.npd.co/realms/platform}"
CLIENT_ID="${OIDC_CLIENT_ID:-ocp-console}"
SECRET="${OCP_OIDC_CLIENT_SECRET:-}"
IDP_NAME="${OCP_OIDC_IDP_NAME:-keycloak}"
SECRET_NAME="${OCP_OIDC_SECRET_NAME:-keycloak-oidc-client}"
CA_CM="${OCP_OIDC_CA_CONFIGMAP:-}" # optional: ConfigMap trong openshift-config chứa key ca.crt

if [[ -z "$SECRET" ]]; then
  echo "ERROR: set OCP_OIDC_CLIENT_SECRET" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 required" >&2
  exit 1
fi

echo "==> Backup OAuth CR"
oc get oauth cluster -o yaml >"/tmp/oauth-cluster.backup.$(date +%Y%m%d%H%M%S).yaml"

echo "==> Secret ${SECRET_NAME} in openshift-config"
oc create secret generic "$SECRET_NAME" \
  -n openshift-config \
  --from-literal=clientSecret="$SECRET" \
  --dry-run=client -o yaml | oc apply -f -

echo "==> Merge identityProviders (name=${IDP_NAME})"
ISSUER="$ISSUER" CLIENT_ID="$CLIENT_ID" IDP_NAME="$IDP_NAME" SECRET_NAME="$SECRET_NAME" CA_CM="$CA_CM" \
python3 - <<'PY' | oc apply -f -
import json, os, subprocess, sys, yaml

issuer = os.environ["ISSUER"]
client_id = os.environ["CLIENT_ID"]
idp_name = os.environ["IDP_NAME"]
secret_name = os.environ["SECRET_NAME"]
ca_cm = os.environ.get("CA_CM") or ""

raw = subprocess.check_output(["oc", "get", "oauth", "cluster", "-o", "json"], text=True)
doc = json.loads(raw)
spec = doc.setdefault("spec", {})
providers = list(spec.get("identityProviders") or [])

providers = [p for p in providers if p.get("name") != idp_name]

openid = {
    "clientID": client_id,
    "clientSecret": {"name": secret_name},
    "claims": {
        "preferredUsername": ["preferred_username"],
        "name": ["name"],
        "email": ["email"],
        "groups": ["groups"],
    },
    "issuer": issuer,
}
if ca_cm:
    openid["ca"] = {"name": ca_cm}

providers.append(
    {
        "name": idp_name,
        "mappingMethod": "claim",
        "type": "OpenID",
        "openID": openid,
    }
)
spec["identityProviders"] = providers

# Strip status / managed fields noise for apply
out = {
    "apiVersion": "config.openshift.io/v1",
    "kind": "OAuth",
    "metadata": {"name": "cluster"},
    "spec": spec,
}
yaml.safe_dump(out, sys.stdout, default_flow_style=False, sort_keys=False)
PY

echo
echo "OK — đợi vài chục giây (oauth-openshift pods restart)."
echo "Console: chọn IdP '${IDP_NAME}' → Keycloak."
echo "Redirect Keycloak phải đúng:"
echo "  https://oauth-openshift.apps.ocp01.npd.co/oauth2callback/${IDP_NAME}"
echo
echo "Nếu login lỗi TLS (x509): tạo ConfigMap CA Keycloak trong openshift-config rồi:"
echo "  export OCP_OIDC_CA_CONFIGMAP=<cm-name> && re-run script"
echo
echo "Lab admin (sau SSO lần đầu):"
echo "  oc adm policy add-cluster-role-to-user cluster-admin <username>"
