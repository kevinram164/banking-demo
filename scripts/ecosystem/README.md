# Ecosystem cron runner — finance + shop traffic

Server riêng gọi API `npd-banking.co` + `npd-shop.co` theo lịch.

| Job | Script | Cron |
|-----|--------|------|
| Seed users (+ Ly) | `job_seed_users.py` | Chủ nhật 03:00 |
| Peer CK (PENDING→confirm) | `job_peer_transfers.py` | mỗi 10 phút |
| Mua shop (MERCHANT_PAY→confirm) | `job_shop_buy.py` | mỗi 3 giờ |
| Ly nhập hàng | `job_ly_restock.py` | 12:00 & 18:00 |
| Finance (DISBURSEMENT/REPAYMENT/FEE) | `job_finance_flows.py` | mỗi giờ `:15` |
| Settle PENDING tồn (admin) | `job_settle_pending.py` | mỗi 15 phút |

Transfer mặc định tạo **PENDING + hold**, rồi job **confirm** (một tỷ lệ nhỏ cancel / leave để expire).

**Không cần chạy settle tay mỗi ngày** nếu cron đã cài. Phân vai:

| Cơ chế | Việc gì |
|--------|---------|
| Peer/shop/finance | Confirm ngay trong job (flow chuẩn) |
| `transfer-service` `hold_expire_loop` | Tự **EXPIRED** khi quá `hold_until` (nhả hold) |
| Cron `settle` | Admin **confirm** hàng loạt PENDING còn treo (lab / backlog) |

## Tham số lab

| Key | Default |
|-----|---------|
| Pass | `123456` |
| SĐT | bắt đầu `09` |
| User balance | 10.000.000 |
| Ly balance | 50.000.000 |
| Peer amount | 50.000 – 500.000 |
| `TRANSFER_CONFIRM_DELAY` | 2s |
| Giá nhập | 70% `price_vnd` catalog |

Ops users (finance job tự tạo): `ops-disburse` `0910000001`, `ops-fee` `0910000002`.

## Deploy server

```bash
cd banking-demo/scripts/ecosystem
sudo bash install.sh

vi /home/sysadmin/npd-ecosystem/.env

/home/sysadmin/npd-ecosystem/bin/run-job.sh seed
/home/sysadmin/npd-ecosystem/bin/run-job.sh peer
/home/sysadmin/npd-ecosystem/bin/run-job.sh shop
/home/sysadmin/npd-ecosystem/bin/run-job.sh finance
/home/sysadmin/npd-ecosystem/bin/run-job.sh restock
# dọn backlog một lần (sau đó cron */15 lo)
SETTLE_MODE=confirm SETTLE_LIMIT=2000 /home/sysadmin/npd-ecosystem/bin/run-job.sh settle
```

Rebuild/sync trước khi chạy cron:

- `transfer-service` — hold/pending + confirm/cancel + MESSAGE_EXPIRED
- `account-service` — available/held + `/me/transfers`
- `api-producer` — `published_at` trên message
- `frontend` — statement UI

## Tài nguyên gợi ý

Runner: 2–4 vCPU / 4–8 GB. Load chính nằm trên Kong / transfer / Postgres cluster.
