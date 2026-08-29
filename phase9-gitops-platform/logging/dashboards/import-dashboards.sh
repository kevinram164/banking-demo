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

# Refresh index pattern field list (event, kubernetes.*, …) — thiếu bước này KQL/Lucene trả 0 hit.
refresh_index_pattern() {
  local id="$1"
  local pattern="$2"
  echo "Refreshing index pattern fields: ${id} (${pattern}) ..."
  OS_DASHBOARDS_URL="$OS_DASHBOARDS_URL" VERIFY_TLS="$VERIFY_TLS" \
    python3 - "$id" "$pattern" <<'PY'
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

pattern_id, pattern_title = sys.argv[1], sys.argv[2]
base = os.environ["OS_DASHBOARDS_URL"].rstrip("/")
verify = os.environ.get("VERIFY_TLS", "0").lower() not in ("0", "false", "no", "off")
ctx = ssl.create_default_context() if verify else ssl._create_unverified_context()

def req(method, path, body=None):
    url = f"{base}{path}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "osd-xsrf": "true",
            "securitytenant": "global",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(r, context=ctx, timeout=120) as resp:
        return json.loads(resp.read().decode())

q = urllib.parse.urlencode(
    {
        "pattern": pattern_title,
        "meta_fields": ["_source", "_id", "_index", "_score"],
    },
    doseq=True,
)
fields_resp = req("GET", f"/api/index_patterns/_fields_for_wildcard?{q}")
fields = fields_resp.get("fields") or []
put_body = {
    "attributes": {
        "title": pattern_title,
        "timeFieldName": "@timestamp",
        "fields": json.dumps(fields),
    }
}
req("PUT", f"/api/saved_objects/index-pattern/{pattern_id}?overwrite=true", put_body)
print(f"  OK — {len(fields)} fields")
PY
}

refresh_index_pattern "logs-bank-pattern" "logs-bank-*"
refresh_index_pattern "logs-shop-pattern" "logs-shop-*"

echo ""
echo "Done. Open Dashboards → Dashboard → 'NPD — Banking & Shop (logs)'"
echo "Time range mặc định: Last 24 hours. Nếu vẫn trống → Discover test query: event:transfer_success"
