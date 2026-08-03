# Banking services — sự cố = triệu chứng (5xx / log), không phải “replicas=0”

Ns: `npd-banking`. REST: **Kong → api-producer → RabbitMQ → consumer → Redis**.

## Hiểu đúng lab

`replicas: 0` chỉ **giả lập** “service không chạy”.  
Alert gửi Telegram phải dựa trên **triệu chứng khi user gọi API**:

| Service chết (giả lập scale 0) | User gọi | HTTP (api-producer) | Log (OpenSearch) | Alert Tele |
|-------------------------------|----------|---------------------|------------------|------------|
| **transfer-service** | `POST /api/transfer/transfer` | **504** (timeout) hoặc 502 | `producer_timeout` / `producer_error`, path chứa transfer | `BankingTransferGatewayTimeout`, `BankingTransfer5xx` |
| **auth-service** | `POST /api/auth/login` | **504** / 5xx | `producer_timeout` path auth | `BankingAuthGatewayTimeout`, `BankingAuth5xx` |
| **account-service** | `GET /api/account/balance` | **504** / 5xx | `producer_timeout` path account | `BankingAccountGatewayTimeout`, `BankingAccount5xx` |
| **api-producer** | mọi `/api` | Kong lỗi / không scrape | — | Không có 504 từ producer; hint kube `BankingApiReplicasZero` |

Code: `phase8-application-v3/producer/main.py` — `TimeoutError` → log `producer_timeout` + status **504**.

**Không gọi API** (im traffic) → **không có 5xx** → không có alert triệu chứng. Phải gọi thử (curl / ecosystem) sau khi “làm hỏng” service.

## Chức năng & blast radius

| Service | Chức năng | User mất gì khi chết |
|---------|-----------|----------------------|
| api-producer | Cổng `/api/*` → queue | Mọi REST banking |
| auth-service | login/register | Không đăng nhập |
| account-service | me/balance/lookup | Không số dư/tra STK |
| transfer-service | P2P CK + shop NOLI | Không chuyển tiền / shop pay |
| notification-service | WS + list notify | Mất realtime (CK vẫn OK) |
| shop-bridge | Kafka + confirm | Shop không `payment.completed` |

## Log vs metric

Cùng một sự cố timeout:

```text
log  producer_timeout  ──►  OpenSearch Discover (điều tra)
         │
         └── HTTP 504  ──►  http_requests_total{status="504"}  ──►  PrometheusRule  ──►  Telegram
```

Alertmanager **không đọc** OpenSearch trực tiếp; 504 trên metric = tín hiệu đã “đóng gói” từ cùng lỗi ghi log.

## Test transfer “hỏng”

```bash
# 1) Giả lập sự cố
oc -n npd-banking scale deploy/transfer-service --replicas=0
# (hoặc Helm replicas: 0 + sync)

# 2) Tạo triệu chứng — BẮT BUỘC gọi API (vài lần)
# login lấy session rồi:
curl -sk -X POST https://npd-banking.co/api/transfer/transfer \
  -H "Content-Type: application/json" -H "X-Session: $SESSION" \
  -d '{"amount":1000,"to_account_number":"STK","note":"test"}'
# Kỳ vọng body: Gateway timeout, HTTP 504

# 3) ~1–2 phút → Tele: BankingTransferGatewayTimeout / BankingTransfer5xx
# OpenSearch: event producer_timeout

# 4) Restore
oc -n npd-banking scale deploy/transfer-service --replicas=1
```
