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
#   CURL_OPTS   - Thêm tùy chọn curl (vd: CURL_OPTS="-s -k" cho self-signed cert)

COUNT=${1:-1000}
BASE_URL=${2:-https://npd-banking.co}
PASSWORD="${PASSWORD:-Test123456}"
ENDPOINT="${BASE_URL}/api/auth/register"
PARALLEL=${PARALLEL:-20}
USER_PREFIX="${USER_PREFIX:-user}"
CURL_OPTS="${CURL_OPTS:--s}"

# Số chữ số để zero-pad (1000 → 4, 100 → 3)
PAD=${#COUNT}

echo "=== Seed Users ==="
echo "Count:    $COUNT"
echo "Base URL: $BASE_URL"
echo "Endpoint: $ENDPOINT"
echo "Parallel: $PARALLEL"
echo ""

register_one() {
  local i=$1
  local username="${USER_PREFIX}_$(printf "%0${PAD}d" "$i")"
  local body="{\"username\":\"$username\",\"password\":\"$PASSWORD\"}"
  local code
  local out

  out=$(curl $CURL_OPTS -w "\n%{http_code}" -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$body" 2>/dev/null || echo "000")
  code=$(echo "$out" | tail -n1)

  case "$code" in
    200) echo "OK" ;;
    409) echo "SKIP" ;;
    *)   echo "FAIL" ;;
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
FAILED=$(grep -c "^FAIL$" "$LOG" 2>/dev/null || true)
[ -z "$SUCCESS" ] && SUCCESS=0
[ -z "$SKIPPED" ] && SKIPPED=0
[ -z "$FAILED" ] && FAILED=0

echo ""
echo "=== Kết quả ==="
echo "Thành công: $SUCCESS"
echo "Đã tồn tại: $SKIPPED"
echo "Thất bại:  $FAILED"
echo ""
echo "Kiểm tra DB:"
echo "  kubectl exec -n postgres postgres-postgresql-primary-0 -- psql -U banking -d banking -t -c 'SELECT count(*) FROM users;'"
