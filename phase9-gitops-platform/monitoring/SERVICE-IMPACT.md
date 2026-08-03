# Banking services — sự cố = 503 Service Unavailable (+ log), không phải replicas=0

Ns: `npd-banking`. REST: **Kong → api-producer → RabbitMQ → consumer → Redis**.

## Hiểu đúng lab

`replicas: 0` chỉ **giả lập** “service không chạy”.  
Khi consumer không trả lời trong `RABBITMQ_RESPONSE_TIMEOUT` (~20s):

| | |
|--|--|
| HTTP | **503** Service Unavailable |
| Body | `Service unavailable: no response from transfer.requests within timeout` |
| Log | `downstream_unavailable` (OpenSearch) |
| Alert Tele | `BankingTransferUnavailable` / `Banking*5xx` |

| Service chết | User gọi | HTTP | Log | Alert |
|--------------|----------|------|-----|-------|
| **transfer-service** | `POST /api/transfer/transfer` | **503** | `downstream_unavailable` | `BankingTransferUnavailable` |
| **auth-service** | `POST /api/auth/login` | **503** | `downstream_unavailable` | `BankingAuthUnavailable` |
| **account-service** | `GET /api/account/balance` | **503** | `downstream_unavailable` | `BankingAccountUnavailable` |

**HTTP 000 / Empty reply @ ~60s:** Kong `read_timeout` cắt trước khi producer trả body.  
Producer timeout phải **nhỏ hơn** Kong (20s < 30s). Log vẫn có trên pod `api-producer` (`downstream_unavailable` / image cũ: `producer_timeout`).

Code: `producer/main.py` — `TimeoutError` → **503** (không còn 504). Cần **rebuild image api-producer** rồi sync.

## Chức năng & blast radius

| Service | User mất gì khi chết |
|---------|----------------------|
| api-producer | Mọi REST banking |
| auth-service | Login/register |
| account-service | Số dư / lookup |
| transfer-service | CK / shop pay |
| notification-service | WS / lịch sử notify |
| shop-bridge | Confirm thanh toán shop |

## Test transfer “hỏng”

```bash
oc -n npd-banking scale deploy/transfer-service --replicas=0

curl -sk --max-time 30 -w "\nHTTP %{http_code}\n" \
  -X POST https://npd-banking.co/api/transfer/transfer \
  -H "Content-Type: application/json" -H "X-Session: $SESSION" \
  -d '{"amount":1000,"to_account_number":"638607571915","note":"test"}'
# Kỳ vọng ~20s → HTTP 503

# Tele: BankingTransferUnavailable
oc -n npd-banking scale deploy/transfer-service --replicas=1
```
