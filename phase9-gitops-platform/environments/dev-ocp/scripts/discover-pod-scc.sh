#!/usr/bin/env bash
# In ServiceAccount + runAsUser + SCC event cho pod Pending/Forbidden trong namespace
set -euo pipefail
NS="${1:-argocd}"

echo "=== Namespace UID range ==="
oc get ns "$NS" -o jsonpath='{.metadata.annotations.openshift\.io/sa\.scc\.uid-range}{"\n"}' 2>/dev/null || echo "(no annotation)"

echo ""
echo "=== Pods not Running ==="
oc get pods -n "$NS" --field-selector=status.phase!=Running -o name 2>/dev/null | while read -r pod; do
  name="${pod#pod/}"
  echo "--- $name ---"
  oc get pod "$name" -n "$NS" -o jsonpath='  SA: {.spec.serviceAccountName}{"\n"}'
  oc get pod "$name" -n "$NS" -o jsonpath='  pod runAsUser: {.spec.securityContext.runAsUser}{"\n"}' 2>/dev/null
  oc get pod "$name" -n "$NS" -o jsonpath='  container[0] runAsUser: {.spec.containers[0].securityContext.runAsUser}{"\n"}' 2>/dev/null
  echo "  Events (SCC):"
  oc get events -n "$NS" --field-selector "involvedObject.name=$name" \
    | grep -iE 'scc|security|forbidden|uid' | tail -3 | sed 's/^/    /' || echo "    (none)"
  echo ""
done

echo "=== ServiceAccounts in $NS ==="
oc get sa -n "$NS" -o custom-columns=NAME:.metadata.name --no-headers
