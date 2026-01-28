#!/usr/bin/env bash
# Chạy lần lượt các kịch bản load test (auth, account, transfer).
# Dùng BASE_URL, VUS, DURATION từ env hoặc mặc định.

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
VUS="${VUS:-10}"
DURATION="${DURATION:-2m}"

echo "BASE_URL=$BASE_URL VUS=$VUS DURATION=$DURATION"
echo "---"

echo "[1/3] k6-auth.js (Auth service)"
k6 run --vus "$VUS" --duration "$DURATION" -e BASE_URL="$BASE_URL" k6-auth.js
echo ""

echo "[2/3] k6-account.js (Account service)"
k6 run --vus "$VUS" --duration "$DURATION" -e BASE_URL="$BASE_URL" k6-account.js
echo ""

echo "[3/3] k6-transfer.js (Transfer service)"
k6 run --vus "$VUS" --duration "$DURATION" -e BASE_URL="$BASE_URL" k6-transfer.js
echo ""

echo "Done. Kiểm tra KEDA: kubectl get pods -n banking && kubectl get hpa -n banking"
