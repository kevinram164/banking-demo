#!/usr/bin/env bash
# Cài ecosystem runner lên server mới (Ubuntu/RHEL).
# Chạy với quyền root hoặc sudo.
set -euo pipefail

ROOT="${ECOSYSTEM_ROOT:-/opt/npd-ecosystem}"
REPO_SCRIPTS="$(cd "$(dirname "$0")" && pwd)"

echo "==> Install dir: ${ROOT}"
mkdir -p "${ROOT}/bin" "${ROOT}/data" "${ROOT}/logs"

# Copy jobs
cp -a "${REPO_SCRIPTS}/"*.py "${ROOT}/bin/" 2>/dev/null || true
# common + jobs
for f in common.py job_seed_users.py job_peer_transfers.py job_shop_buy.py job_ly_restock.py; do
  cp -f "${REPO_SCRIPTS}/${f}" "${ROOT}/bin/${f}"
done

if [[ ! -f "${ROOT}/.env" ]]; then
  cp "${REPO_SCRIPTS}/config.env.example" "${ROOT}/.env"
  echo "Created ${ROOT}/.env — chỉnh BANK_URL / SHOP_URL / LY_ACCOUNT_NUMBER"
else
  echo "Keep existing ${ROOT}/.env"
fi

# Python venv
if [[ ! -d "${ROOT}/venv" ]]; then
  python3 -m venv "${ROOT}/venv"
fi
"${ROOT}/venv/bin/pip" install -q --upgrade pip
"${ROOT}/venv/bin/pip" install -q -r "${REPO_SCRIPTS}/requirements.txt"

# Wrapper
cat > "${ROOT}/bin/run-job.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT=/opt/npd-ecosystem
export ECOSYSTEM_ENV="${ECOSYSTEM_ENV:-$ROOT/.env}"
JOB="${1:?job name: seed|peer|shop|restock}"
LOG_DIR="${ROOT}/logs"
mkdir -p "$LOG_DIR"
TS="$(date +%Y%m%d-%H%M%S)"
case "$JOB" in
  seed)    PY=job_seed_users.py ;;
  peer)    PY=job_peer_transfers.py ;;
  shop)    PY=job_shop_buy.py ;;
  restock) PY=job_ly_restock.py ;;
  *) echo "unknown job: $JOB"; exit 2 ;;
esac
exec >>"${LOG_DIR}/${JOB}-${TS}.log" 2>&1
echo "==== $(date -Is) start ${JOB} ===="
cd "$ROOT"
set -a
# shellcheck disable=SC1091
source "$ECOSYSTEM_ENV"
set +a
set +e
"${ROOT}/venv/bin/python" "${ROOT}/bin/${PY}"
rc=$?
set -e
echo "==== $(date -Is) end ${JOB} rc=${rc} ===="
exit "$rc"
EOF
chmod +x "${ROOT}/bin/run-job.sh"

# Crontab
CRON_FILE=/etc/cron.d/npd-ecosystem
cat > "${CRON_FILE}" <<EOF
# NPD ecosystem — 4 kịch bản
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""

# 1) Seed users — Chủ nhật 03:00
0 3 * * 0 root ${ROOT}/bin/run-job.sh seed

# 2) Peer CK — mỗi 10 phút
*/10 * * * * root ${ROOT}/bin/run-job.sh peer

# 3) Mua shop — mỗi 3 giờ
0 */3 * * * root ${ROOT}/bin/run-job.sh shop

# 4) Ly nhập hàng — 12:00 & 18:00
0 12,18 * * * root ${ROOT}/bin/run-job.sh restock
EOF
chmod 644 "${CRON_FILE}"

echo
echo "OK. Tiếp theo:"
echo "  1. vi ${ROOT}/.env"
echo "  2. ${ROOT}/bin/run-job.sh seed     # tạo Ly + batch users"
echo "  3. Điền LY_ACCOUNT_NUMBER vào .env + GitOps merchant STK"
echo "  4. ${ROOT}/bin/run-job.sh peer|shop|restock  # smoke test"
echo "  5. tail -f ${ROOT}/logs/*.log"
