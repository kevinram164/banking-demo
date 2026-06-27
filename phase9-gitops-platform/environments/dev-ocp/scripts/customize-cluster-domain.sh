#!/usr/bin/env bash
# Thay CLUSTER_DOMAIN trong manifest dev-ocp bằng domain OpenShift thật
set -euo pipefail
DOMAIN="${1:-}"
if [[ -z "$DOMAIN" ]]; then
  DOMAIN="$(oc get ingresses.config cluster -o jsonpath='{.spec.domain}' 2>/dev/null || true)"
fi
if [[ -z "$DOMAIN" ]]; then
  echo "Usage: $0 <cluster-domain>"
  echo "  vd: $0 apps.ocp.example.com"
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "CLUSTER_DOMAIN=$DOMAIN"
find "$ROOT" -type f \( -name '*.yaml' -o -name '*.md' -o -name '*.sh' \) -print0 \
  | xargs -0 sed -i "s/CLUSTER_DOMAIN/${DOMAIN//\//\\/}/g"
echo "Done. Review: git diff $ROOT"
