#!/usr/bin/env bash
# Import saved searches + dashboard vào OpenSearch Dashboards (lab).
#
# Lab OCP Route thường dùng cert self-signed → mặc định curl -k.
# Prod: VERIFY_TLS=1 bash import-dashboards.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NDJSON="${SCRIPT_DIR}/saved-objects.ndjson"
OS_DASHBOARDS_URL="${OS_DASHBOARDS_URL:-https://logs-platform.apps.ocp01.npd.co}"

# 1 / true / yes = verify TLS (prod). Mặc định lab: không verify.
VERIFY_TLS="${VERIFY_TLS:-0}"
CURL_EXTRA=()
if [[ "$VERIFY_TLS" =~ ^(0|false|no|off)$ ]]; then
  CURL_EXTRA+=(-k)
fi

if [[ ! -f "$NDJSON" ]]; then
  echo "Missing $NDJSON" >&2
  exit 1
fi

echo "Importing to ${OS_DASHBOARDS_URL} (VERIFY_TLS=${VERIFY_TLS}) ..."
curl -sS "${CURL_EXTRA[@]}" -X POST \
  "${OS_DASHBOARDS_URL}/api/saved_objects/_import?overwrite=true" \
  -H "osd-xsrf: true" \
  -H "securitytenant: global" \
  --form "file=@${NDJSON}" | head -c 4000
echo ""
echo "Done. Open Dashboards → Dashboard → 'NPD — Banking & Shop (logs)'"
echo "Nếu 422 migration version: kiểm tra OSD — saved-objects.ndjson dùng migration 7.6.0 / 7.9.3"
