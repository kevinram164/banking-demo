# Banking services — chức năng & ảnh hưởng khi lỗi

Ns: `npd-banking`. Luồng REST: **Kong `/api` → api-producer → RabbitMQ → consumer → Redis reply**.

```text
Client / Shop
    │
    ▼
  Kong ──/api/*──► api-producer ──publish──► RabbitMQ queues
                       │                         │
                       │ wait Redis reply         ▼
                       │              auth | account | transfer | notification
                       ▼
                  Redis correlation

  Kong ──/ws──► notification-service (realtime)
  Kafka orders.events ──► shop-bridge ──► payments.events
  transfer-service ──HTTP──► shop-bridge /api/shop/confirm-payment
```

## Bảng chức năng & blast radius

| Service | Deploy | Job (ServiceMonitor) | Chức năng chính | Nếu DOWN — mất gì | Vẫn OK |
|---------|--------|----------------------|-----------------|-------------------|--------|
| **api-producer** | `api-producer` | `banking-api-producer` | Gateway nội bộ: map `/api/auth\|account\|transfer\|notifications/*` → queue, chờ Redis | **Mọi REST banking qua Kong** (login, số dư, CK, lịch sử notify qua producer). Shop gọi bank API fail | WS `/ws` nếu notification còn; Kafka shop-bridge độc lập |
| **auth-service** | `auth-service` | `banking-auth` | Consumer `auth.requests`: register, login | **Đăng ký / đăng nhập** mới. Session mới không tạo được → me/balance/CK cũng fail nếu chưa login | Session Redis còn hạn; WS nếu đã có session |
| **account-service** | `account-service` | `banking-account` | Consumer `account.requests`: me, balance, lookup, admin credit/stats | **Xem số dư / profile / tra STK**; admin credit; UI CK thiếu lookup người nhận | Login; CK nếu đã biết STK (transfer vẫn chạy) |
| **transfer-service** | `transfer-service` | `banking-transfer` | Consumer `transfer.requests`: P2P CK; ghi DB; notify Redis; confirm shop (`NOLI-*`) | **Chuyển tiền P2P**; shop thanh toán treo (không debit / không confirm) | Login, xem số dư, WS |
| **notification-service** | `notification-service` | `banking-notification` | Consumer list notify; HTTP `/api/notifications`; **WS `/ws`** | **Realtime toast / lịch sử thông báo** | Login, số dư, CK vẫn thành công (user không thấy push) |
| **shop-bridge** | `shop-bridge` | `banking-shop-bridge` | Kafka `orders.events` → `payments.events`; HTTP confirm-payment | **Checkout shop / payment.completed**; đơn treo “chờ CK” | Banking P2P thuần; login/balance |

## Feature → services bắt buộc UP

| Tính năng người dùng | Cần UP |
|----------------------|--------|
| Đăng ký / Đăng nhập | Kong, api-producer, RabbitMQ, Redis, Postgres, **auth-service** |
| Xem số dư / me / lookup STK | … + **account-service** |
| Chuyển tiền P2P | … + **transfer-service** (+ Redis notify) |
| Thông báo realtime | Kong `/ws`, **notification-service**, Redis |
| Lịch sử thông báo | api-producer path **hoặc** Kong direct → **notification-service** |
| Shop mua hàng (CK merchant + `NOLI-*`) | **transfer-service** + **shop-bridge** + Kafka (+ api-producer nếu gọi bank API) |

## Mapping alert (rules trong `prometheusrules/`)

| Khi lỗi | Alert | Severity | Ý nghĩa nghiệp vụ |
|---------|-------|----------|-------------------|
| Transfer HTTP 4xx/5xx cao (API còn sống) | `BankingTransferHighFailureRate` | critical | Chuyển tiền thất bại |
| api-producer down / replicas=0 | `BankingApiDown` / `BankingApiScaledToZero` | critical | Toàn bộ API banking tắt |
| auth down / replicas=0 | `BankingAuthDown` / `BankingAuthScaledToZero` | critical | Không đăng nhập được |
| account down / replicas=0 | `BankingAccountDown` / `BankingAccountScaledToZero` | warning | Không xem số dư / lookup |
| transfer down / replicas=0 | `BankingTransferDown` / `BankingTransferScaledToZero` | critical | Không chuyển tiền / shop CK |
| notification down / replicas=0 | `BankingNotificationDown` / `BankingNotificationScaledToZero` | warning | Mất realtime / lịch sử notify |
| shop-bridge down / replicas=0 | `BankingShopBridgeDown` / `BankingShopBridgeScaledToZero` | critical | Shop không confirm thanh toán |

**Ghi chú kỹ thuật**

- Tầng nghiệp vụ (HTTP `status` trên path transfer) chỉ fire khi **còn traffic**.
- Scale `replicas=0` → dùng rule **kube** (`spec_replicas==0`) cho chắc; `up==0` bổ sung khi scrape còn target.
- Không dùng `absent(up)` cho consumer (dễ ảo); chỉ api-producer giữ `absent` vì là cổng duy nhất.
