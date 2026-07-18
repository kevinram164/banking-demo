#!/usr/bin/env bash
# Jenkins OIDC → Keycloak (lab: mọi user SSO = admin Jenkins)
#
# Keycloak trước:
#   Client ID: jenkins (confidential)
#   Redirect: https://jenkins-platform.apps.ocp01.npd.co/securityRealm/finishLogin
#   Web origin: https://jenkins-platform.apps.ocp01.npd.co
#   Mapper Group Membership → claim groups
#
# Usage:
#   export JENKINS_OIDC_CLIENT_SECRET='...'
#   ./jenkins-oidc-keycloak.sh
# Sau đó sync Argo app platform-jenkins (values đã có oic-auth + JCasC).
set -euo pipefail

NS="${JENKINS_NAMESPACE:-platform}"
SECRET="${JENKINS_OIDC_CLIENT_SECRET:-}"

if [[ -z "$SECRET" ]]; then
  echo "ERROR: set JENKINS_OIDC_CLIENT_SECRET" >&2
  exit 1
fi

echo "==> Create/update secret jenkins-oidc-keycloak (ns=${NS})"
oc create secret generic jenkins-oidc-keycloak -n "$NS" \
  --from-literal=client-secret="${SECRET}" \
  --dry-run=client -o yaml | oc apply -f -

echo "OK — secret sẵn sàng. Sync Jenkins:"
echo "  argocd app sync platform-jenkins"
echo "  (hoặc đợi auto-sync)"
echo "Login: https://jenkins-platform.apps.ocp01.npd.co → Login with Keycloak"
echo "Mọi user SSO = admin (loggedInUsersCanDoAnything)."
