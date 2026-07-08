#!/usr/bin/env bash
# Gán SCC jenkins-kaniko-root cho SA jenkins-kaniko (Kaniko cần UID 0 trên OCP).
# Chạy trên bastion (đã oc login):
#   ./environments/dev-ocp/scripts/jenkins-kaniko-scc-setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NS="${PLATFORM_NS:-platform}"
SA="${JENKINS_AGENT_SA:-jenkins-kaniko}"

echo "==> SA ${SA} trong ns ${NS}"
oc create serviceaccount "${SA}" -n "${NS}" --dry-run=client -o yaml | oc apply -f -

echo "==> Apply SCC jenkins-kaniko-root"
oc apply -f "${ROOT}/ocp-values/scc/jenkins-kaniko-scc.yaml"

echo "==> Bind SCC → SA (users[] trong YAML + scc-subject)"
oc adm policy add-scc-to-user jenkins-kaniko-root \
  -z "${SA}" \
  -n "${NS}"

echo "==> Verify"
oc get scc jenkins-kaniko-root -o jsonpath='{.users}{"\n"}'
oc describe sa "${SA}" -n "${NS}" | head -20

echo "OK — rebuild Jenkins pipeline (Kaniko container runAsUser: 0)."
