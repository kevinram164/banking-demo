#!/usr/bin/env bash
# Cài ecosystem runner (mặc định: /home/sysadmin/npd-ecosystem).
#   sudo bash install.sh
#   ECOSYSTEM_ROOT=/other/path sudo bash install.sh
set -euo pipefail

ROOT="${ECOSYSTEM_ROOT:-/home/sysadmin/npd-ecosystem}"
REPO_SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
RUN_USER="${ECOSYSTEM_USER:-sysadmin}"

echo "==> Install dir: ${ROOT}"
mkdir -p "${ROOT}/bin" "${ROOT}/data" "${ROOT}/logs"

for f in common.py job_seed_users.py job_peer_transfers.py job_shop_buy.py job_ly_restock.py job_finance_flows.py job_settle_pending.py; do
  cp -f "${REPO_SCRIPTS}/${f}" "${ROOT}/bin/${f}"
done

if [[ ! -f "${ROOT}/.env" ]]; then
  cp "${REPO_SCRIPTS}/config.env.example" "${ROOT}/.env"
  # Ghi đè path data/log theo ROOT
  sed -i "s|^DATA_DIR=.*|DATA_DIR=${ROOT}/data|" "${ROOT}/.env"
  sed -i "s|^LOG_DIR=.*|LOG_DIR=${ROOT}/logs|" "${ROOT}/.env"
  echo "Created ${ROOT}/.env — chỉnh BANK_URL / SHOP_URL / LY_ACCOUNT_NUMBER"
else
  echo "Keep existing ${ROOT}/.env"
fi

if [[ ! -x "${ROOT}/venv/bin/python" ]] || [[ ! -e "${ROOT}/venv/bin/pip" && ! -e "${ROOT}/venv/bin/pip3" ]]; then
  echo "==> (Re)create venv at ${ROOT}/venv"
  rm -rf "${ROOT}/venv"
  if ! python3 -m venv "${ROOT}/venv"; then
    echo "FAIL: python3 -m venv — cài: apt install -y python3-venv python3-pip"
    exit 1
  fi
fi
PY="${ROOT}/venv/bin/python"
"$PY" -m ensurepip --upgrade 2>/dev/null || true
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r "${REPO_SCRIPTS}/requirements.txt"

# Wrapper — embed ROOT thật (không hardcode /opt)
cat > "${ROOT}/bin/run-job.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
ROOT="${ROOT}"
export ECOSYSTEM_ENV="\${ECOSYSTEM_ENV:-\$ROOT/.env}"
JOB="\${1:?job name: seed|peer|shop|restock|finance|settle}"
LOG_DIR="\$ROOT/logs"
mkdir -p "\$LOG_DIR"
TS="\$(date +%Y%m%d-%H%M%S)"
case "\$JOB" in
  seed)    PY=job_seed_users.py ;;
  peer)    PY=job_peer_transfers.py ;;
  shop)    PY=job_shop_buy.py ;;
  restock) PY=job_ly_restock.py ;;
  finance) PY=job_finance_flows.py ;;
  settle)  PY=job_settle_pending.py ;;
  *) echo "unknown job: \$JOB"; exit 2 ;;
esac
exec >>"\${LOG_DIR}/\${JOB}-\${TS}.log" 2>&1
echo "==== \$(date -Is) start \${JOB} ===="
cd "\$ROOT"
set -a
# shellcheck disable=SC1091
source "\$ECOSYSTEM_ENV"
set +a
set +e
"\${ROOT}/venv/bin/python" "\${ROOT}/bin/\${PY}"
rc=\$?
set -e
echo "==== \$(date -Is) end \${JOB} rc=\${rc} ===="
exit "\$rc"
EOF
chmod +x "${ROOT}/bin/run-job.sh"

# Quyền cho user chạy (không cần root mỗi lần)
if id "${RUN_USER}" &>/dev/null; then
  chown -R "${RUN_USER}:${RUN_USER}" "${ROOT}"
fi

CRON_FILE=/etc/cron.d/npd-ecosystem
cat > "${CRON_FILE}" <<EOF
# NPD ecosystem — kịch bản (${ROOT})
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""

# 1) Seed users — Chủ nhật 03:00
0 3 * * 0 ${RUN_USER} ${ROOT}/bin/run-job.sh seed

# 2) Peer CK — mỗi 10 phút (PENDING→confirm)
*/10 * * * * ${RUN_USER} ${ROOT}/bin/run-job.sh peer

# 3) Mua shop — mỗi 3 giờ
0 */3 * * * ${RUN_USER} ${ROOT}/bin/run-job.sh shop

# 4) Ly nhập hàng — 12:00 & 18:00
0 12,18 * * * ${RUN_USER} ${ROOT}/bin/run-job.sh restock

# 5) Finance flows (DISBURSEMENT/REPAYMENT/FEE) — mỗi giờ
15 * * * * ${RUN_USER} ${ROOT}/bin/run-job.sh finance

# 6) Settle PENDING tồn (admin confirm) — mỗi 15 phút
#    Peer/shop/finance đã confirm trong job; cron này dọn backlog / leave-pending.
*/15 * * * * ${RUN_USER} SETTLE_MODE=confirm SETTLE_LIMIT=500 ${ROOT}/bin/run-job.sh settle
EOF
chmod 644 "${CRON_FILE}"

echo
echo "OK. Tiếp theo:"
echo "  1. vi ${ROOT}/.env"
echo "  2. ${ROOT}/bin/run-job.sh seed"
echo "  3. Điền LY_ACCOUNT_NUMBER vào .env + GitOps merchant STK"
echo "  4. ${ROOT}/bin/run-job.sh peer|shop|restock|finance|settle"
echo "  5. tail -f ${ROOT}/logs/*.log"
