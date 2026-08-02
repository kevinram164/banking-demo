# Ecosystem cron runner — 4 kịch bản

Server riêng gọi API `npd-banking.co` + `npd-shop.co` theo lịch.

| Job | Script | Cron |
|-----|--------|------|
| Seed users (+ Ly) | `job_seed_users.py` | Chủ nhật 03:00 |
| Peer CK | `job_peer_transfers.py` | mỗi 10 phút |
| Mua shop | `job_shop_buy.py` | mỗi 3 giờ |
| Ly nhập hàng | `job_ly_restock.py` | 12:00 & 18:00 |

## Tham số lab

| Key | Default |
|-----|---------|
| Pass | `123456` |
| SĐT | bắt đầu `09` |
| User balance | 10.000.000 |
| Ly balance | 50.000.000 |
| Peer amount | 50.000 – 500.000 |
| Giá nhập | 70% `price_vnd` catalog |

## Deploy server

```bash
# từ máy có clone banking-demo
cd banking-demo/scripts/ecosystem
sudo bash install.sh

sudo vi /opt/npd-ecosystem/.env   # BANK_URL, SHOP_URL, ADMIN_SECRET

# Smoke
sudo /opt/npd-ecosystem/bin/run-job.sh seed
# copy STK Ly → LY_ACCOUNT_NUMBER + GitOps SHOP_MERCHANT / BANK_ACCOUNT_NUMBER
sudo /opt/npd-ecosystem/bin/run-job.sh peer
sudo /opt/npd-ecosystem/bin/run-job.sh shop
sudo /opt/npd-ecosystem/bin/run-job.sh restock
```

Log: `/opt/npd-ecosystem/logs/`. Users: `/opt/npd-ecosystem/data/users.json`.

Seed mỗi tuần chỉ thêm tối đa `SEED_BATCH` (200) tới khi đủ `TARGET_CUSTOMERS` / `TARGET_SUPPLIERS`.

## Prerequisite OCP

**Logging trước khi chạy job** (OpenSearch): xem `phase9-gitops-platform/logging/DEPLOY.md`  
UI: https://logs-platform.apps.ocp01.npd.co — index `npd-*` (bank / shop / kafka).

Rebuild/sync trước khi chạy cron nặng:

- `auth-service` — `initial_balance` + default 10tr
- `account-service` — `POST /api/account/admin/credit`
- `transfer-service` — `note` + matcher NOLI
- shop `payment-worker` — lz4 nếu còn message cũ

Seed Ly một lần (tương đương job seed):

```bash
python scripts/seed_huongly.py --base-url https://npd-banking.co --insecure
```

## Tài nguyên gợi ý

Runner: 2–4 vCPU / 4–8 GB. Load chính nằm trên Kong / transfer / Postgres cluster.
