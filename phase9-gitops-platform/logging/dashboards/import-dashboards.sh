#!/usr/bin/env bash
# Import saved searches + dashboard vào OpenSearch Dashboards (lab).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NDJSON="${SCRIPT_DIR}/saved-objects.ndjson"
OS_DASHBOARDS_URL="${OS_DASHBOARDS_URL:-https://logs-platform.apps.ocp01.npd.co}"

if [[ ! -f "$NDJSON" ]]; then
  echo "Missing $NDJSON" >&2
  exit 1
fi

echo "Importing to ${OS_DASHBOARDS_URL} ..."
curl -sS -X POST "${OS_DASHBOARDS_URL}/api/saved_objects/_import?overwrite=true" \
  -H "osd-xsrf: true" \
  -H "securitytenant: global" \
  --form file=@"${NDJSON}" | head -c 2000
echo ""
echo "Done. Open Dashboards → Dashboard → 'NPD — Banking & Shop (logs)'"
