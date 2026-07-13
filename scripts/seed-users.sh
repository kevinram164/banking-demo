#!/usr/bin/env bash
# Script giả lập tạo N users qua API register
#
# Dùng:
#   ./seed-users.sh [số_users] [base_url]
#   ./seed-users.sh 1000
#   ./seed-users.sh 500 https://npd-banking.co
#
# Biến môi trường:
#   PASSWORD    - Mật khẩu chung (mặc định: Test123456)
#   PARALLEL    - Số request song song (mặc định: 20)
#   USER_PREFIX - Tiền tố username (mặc định: user) → user_0001, user_0002...
#   CURL_OPTS   - Thêm tùy chọn curl (mặc định: -s -k cho TLS lab OCP)

COUNT=${1:-1000}
BASE_URL=${2:-https://npd-banking.co}
PASSWORD="${PASSWORD:-Test123456}"
ENDPOINT="${BASE_URL}/api/auth/register"
PARALLEL=${PARALLEL:-20}
USER_PREFIX="${USER_PREFIX:-user}"
CURL_OPTS="${CURL_OPTS:--s -k}"

# Số chữ số để zero-pad (1000 → 4, 100 → 3)
PAD=${#COUNT}

echo "=== Seed Users ==="
echo "Count:    $COUNT"
echo "Base URL: $BASE_URL"
echo "Endpoint: $ENDPOINT"
echo "Parallel: $PARALLEL"
echo ""

# Smoke test 1 request trước khi chạy parallel
smoke=$(curl $CURL_OPTS -w "\n%{http_code}" -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${USER_PREFIX}_smoke\",\"password\":\"$PASSWORD\"}" 2>&1)
smoke_code=$(echo "$smoke" | tail -n1)
smoke_body=$(echo "$smoke" | sed '$d')
echo "Smoke POST → HTTP $smoke_code"
echo "Body: ${smoke_body:0:300}"
echo ""
if [[ "$smoke_code" != "200" && "$smoke_code" != "409" ]]; then
  echo "ABORT: API register không OK. Kiểm tra:"
  echo "  curl -sk -i -X POST '$ENDPOINT' -H 'Content-Type: application/json' \\"
  echo "    -d '{\"username\":\"u1\",\"password\":\"Test123456\"}'"
  echo "  oc get pods -n banking"
  echo "  oc get route -n banking | grep npd-banking"
  echo "  oc logs -n banking deploy/api-producer -c api-producer --tail=30"
  exit 1
fi

register_one() {
  local i=$1
  local username="${USER_PREFIX}_$(printf "%0${PAD}d" "$i")"
  local body="{\"username\":\"$username\",\"password\":\"$PASSWORD\"}"
  local code
  local out

  out=$(curl $CURL_OPTS -w "\n%{http_code}" -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$body" 2>/dev/null || echo -e "\n000")
  code=$(echo "$out" | tail -n1)

  case "$code" in
    200) echo "OK" ;;
    409) echo "SKIP" ;;
    *)   echo "FAIL:$code" ;;
  esac
}

export -f register_one
export ENDPOINT PASSWORD USER_PREFIX PAD CURL_OPTS

LOG=$(mktemp)
trap "rm -f $LOG" EXIT

seq 1 "$COUNT" | xargs -P "$PARALLEL" -I {} bash -c 'register_one "$@"' _ {} 2>/dev/null | tee "$LOG"

# Đếm từ file
SUCCESS=$(grep -c "^OK$" "$LOG" 2>/dev/null || true)
SKIPPED=$(grep -c "^SKIP$" "$LOG" 2>/dev/null || true)
FAILED=$(grep -c "^FAIL" "$LOG" 2>/dev/null || true)
[ -z "$SUCCESS" ] && SUCCESS=0
[ -z "$SKIPPED" ] && SKIPPED=0
[ -z "$FAILED" ] && FAILED=0

echo ""
echo "=== Kết quả ==="
echo "Thành công: $SUCCESS"
echo "Đã tồn tại: $SKIPPED"
echo "Thất bại:  $FAILED"
if [[ "$FAILED" -gt 0 ]]; then
  echo "Mẫu lỗi:"
  grep "^FAIL" "$LOG" | sort | uniq -c | head
fi
echo ""
echo "Kiểm tra DB:"
echo "  oc exec -n postgres sts/postgres-ha-postgresql-primary -c postgresql -- \\"
echo "    psql -U banking -d banking -t -c 'SELECT count(*) FROM users;'"
