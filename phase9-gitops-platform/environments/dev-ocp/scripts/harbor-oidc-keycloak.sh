#!/usr/bin/env bash
# Harbor OIDC → Keycloak (lab: mọi user trong group platform-admins = Harbor system admin)
#
# Keycloak trước:
#   Client ID: harbor (confidential)
#   Redirect: https://harbor-platform.apps.ocp01.npd.co/c/oidc/callback
#   Web origin: https://harbor-platform.apps.ocp01.npd.co
#   Mapper Group Membership → claim groups (trên harbor-dedicated)
#   User ∈ group platform-admins
#
# Usage:
#   export HARBOR_OIDC_CLIENT_SECRET='...'
#   ./harbor-oidc-keycloak.sh
set -euo pipefail

NS="${HARBOR_NAMESPACE:-platform}"
DEPLOY="${HARBOR_CORE_DEPLOY:-harbor-core}"
ISSUER="${KEYCLOAK_ISSUER:-https://keycloak-platform.apps.ocp01.npd.co/realms/platform}"
CLIENT_ID="${OIDC_CLIENT_ID:-harbor}"
SECRET="${HARBOR_OIDC_CLIENT_SECRET:-}"
ADMIN_GROUP="${OIDC_ADMIN_GROUP:-platform-admins}"

if [[ -z "$SECRET" ]]; then
  echo "ERROR: set HARBOR_OIDC_CLIENT_SECRET" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 required" >&2
  exit 1
fi

# Tên deploy Harbor core trên cluster
if ! oc get deploy -n "$NS" "$DEPLOY" &>/dev/null; then
  DEPLOY=$(oc get deploy -n "$NS" -o name | grep -E 'harbor.*core' | head -1 | cut -d/ -f2 || true)
fi
if [[ -z "${DEPLOY}" ]]; then
  echo "ERROR: không tìm thấy harbor-core Deployment trong ns ${NS}" >&2
  oc get deploy -n "$NS"
  exit 1
fi

echo "==> Deploy: ${NS}/${DEPLOY}"
echo "    Issuer: ${ISSUER}"
echo "    Admin group: ${ADMIN_GROUP}"

CFG=$(
  ISSUER="$ISSUER" CLIENT_ID="$CLIENT_ID" SECRET="$SECRET" ADMIN_GROUP="$ADMIN_GROUP" python3 - <<'PY'
import json, os
cfg = {
  "auth_mode": "oidc_auth",
  "oidc_name": "Keycloak",
  "oidc_endpoint": os.environ["ISSUER"],
  "oidc_client_id": os.environ["CLIENT_ID"],
  "oidc_client_secret": os.environ["SECRET"],
  "oidc_scope": "openid,profile,email",
  "oidc_verify_cert": False,
  "oidc_auto_onboard": True,
  "oidc_user_claim": "preferred_username",
  "oidc_groups_claim": "groups",
  "oidc_admin_group": os.environ["ADMIN_GROUP"],
}
print(json.dumps(cfg, separators=(",", ":")))
PY
)

echo "==> Set CONFIG_OVERWRITE_JSON on ${DEPLOY}"
oc set env "deploy/${DEPLOY}" -n "$NS" "CONFIG_OVERWRITE_JSON=${CFG}"
oc rollout status "deploy/${DEPLOY}" -n "$NS" --timeout=300s

echo
echo "OK — mở https://harbor-platform.apps.ocp01.npd.co → LOGIN WITH OIDC"
echo "User Keycloak phải thuộc group '${ADMIN_GROUP}' để là Harbor admin."
echo "Local admin Harbor vẫn dùng được khi cần (db auth có thể bị ghi đè — giữ escape qua admin nếu UI cho phép)."
