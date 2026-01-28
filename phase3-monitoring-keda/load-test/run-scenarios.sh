#!/bin/sh
# Chạy lần lượt các kịch bản load test (auth, account, transfer).
# Dùng BASE_URL, VUS, DURATION từ env hoặc mặc định.

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
VUS="${VUS:-10}"
DURATION="${DURATION:-2m}"

run_k6() {
  if command -v k6 >/dev/null 2>&1; then
    k6 "$@"
    return
  fi
  echo "k6 not found -> using Docker (grafana/k6)"
  if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: Neither k6 nor docker is installed."
    echo "Install k6: https://grafana.com/docs/k6/latest/set-up/install-k6/"
    echo "Or install docker and rerun."
    exit 1
  fi
  docker run --rm -i \
    -v "$(pwd):/work" -w /work \
    grafana/k6 "$@"
}

echo "BASE_URL=$BASE_URL VUS=$VUS DURATION=$DURATION"
echo "---"

echo "[1/3] k6-auth.js (Auth service)"
run_k6 run --vus "$VUS" --duration "$DURATION" -e BASE_URL="$BASE_URL" k6-auth.js
echo ""

echo "[2/3] k6-account.js (Account service)"
run_k6 run --vus "$VUS" --duration "$DURATION" -e BASE_URL="$BASE_URL" k6-account.js
echo ""

echo "[3/3] k6-transfer.js (Transfer service)"
run_k6 run --vus "$VUS" --duration "$DURATION" -e BASE_URL="$BASE_URL" k6-transfer.js
echo ""

echo "Done. Kiểm tra KEDA: kubectl get pods -n banking && kubectl get hpa -n banking"
