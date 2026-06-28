#!/usr/bin/env bash
# SCC cho ArgoCD upstream trên OpenShift (lab dev-ocp)
# - anyuid: redis UID 999, dex UID 1001
# - privileged: dex seccomp annotations (OCP 4.20 restricted-v2 chặn seccomp)
# Cần quyền cluster-admin.
set -euo pipefail
NS="${1:-argocd}"

echo "==> Grant SCC to system:serviceaccounts:${NS}"
oc adm policy add-scc-to-group anyuid "system:serviceaccounts:${NS}"
oc adm policy add-scc-to-group privileged "system:serviceaccounts:${NS}"

echo "==> Verify (users/groups on SCC)"
oc get scc anyuid -o jsonpath='{.users}{"\n"}{.groups}{"\n"}' | tr ' ' '\n' | grep "system:serviceaccounts:${NS}" || true
oc get scc privileged -o jsonpath='{.groups}{"\n"}' | tr ' ' '\n' | grep "system:serviceaccounts:${NS}" || true

echo "==> Restart workloads"
oc rollout restart statefulset,deployment,daemonset -n "$NS" 2>/dev/null || true

echo "Done. watch: oc get pods -n $NS"
echo "Nếu dex vẫn fail và không dùng SSO: oc scale deployment argocd-dex-server -n $NS --replicas=0"
