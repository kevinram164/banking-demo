# OpenSearch Dashboards — NPD Ecosystem (bank + shop)

UI lab: https://logs-platform.apps.ocp01.npd.co

Theo dõi **giao dịch banking**, **đơn hàng / thanh toán shop**, **luồng Kafka shop↔bank**.

## 1. Chuẩn bị

### Index patterns (Management → Index patterns)

| Pattern | Namespace | Time field |
|---------|-----------|------------|
| `logs-bank-*` | `npd-banking` | `@timestamp` |
| `logs-shop-*` | `npd-shop` | `@timestamp` |

### Fluent Bit JSON parser

File `logging/values-fluent-bit.yaml`: parser JSON **sau** `rewrite_tag` (tag `logs.bank` / `logs.shop`). Fluent Bit 3.2 **không** hỗ trợ `Condition` trên filter parser — dòng không phải JSON vẫn giữ field `log`.

Sync Argo `logging-fluent-bit` sau khi push Git.

### Log nghiệp vụ (app)

| Nguồn | Event JSON | Ý nghĩa |
|-------|------------|---------|
| transfer-service | `transfer_success` | CK thành công |
| transfer-service | `transfer_pending` | Giữ tiền / chờ confirm |
| transfer-service | `transfer_rejected` | Từ chối (số dư, …) |
| transfer-service | `transfer_cancelled` | User hủy |
| transfer-service | `transfer_expired` | Hết hạn hold |
| transfer-service | `shop_bridge_confirm_ok` | Matcher gọi shop-bridge OK |
| shop-bridge | `shop_order_seen` | Nhận `order.created` từ Kafka |
| shop-bridge | `payment_emitted` | Gửi `payment.completed` |
| order-service | `order_created` | Đặt hàng (pending_payment) |
| order-service | `order_payment_applied` | Đơn đổi trạng thái paid/… |
| payment-worker | `payment_received` | Kafka payment → apply order |

GitOps: `LOG_TRANSFER_JSON=true` (banking), `LOG_BUSINESS_JSON=true` (shop) trong `values-observability.yaml`.

**Rebuild image** transfer-service, shop-bridge, order-service, payment-worker sau khi push.

---

## 2. Import nhanh (saved searches + dashboard)

Trên máy có `curl` + route OpenSearch Dashboards:

```bash
cd banking-demo/phase9-gitops-platform/logging/dashboards

export OS_DASHBOARDS_URL="https://logs-platform.apps.ocp01.npd.co"
# Lab OCP: Route cert self-signed — script mặc định curl -k (VERIFY_TLS=0)
bash import-dashboards.sh
# Prod có CA hợp lệ: VERIFY_TLS=1 bash import-dashboards.sh
```

Vào **Dashboards** → mở **NPD — Banking & Shop (logs)**.

`saved-objects.ndjson` dùng **migrationVersion 7.6.0** (khớp OpenSearch Dashboards 2.x lab). Lỗi `422` / `8.0.0` → pull file mới từ Git.

Import tay: Management → **Saved objects** → **Import** → chọn `saved-objects.ndjson`.

---

## 3. Tạo dashboard thủ công (Visualize)

### A. Banking — Giao dịch theo trạng thái

**Data view:** `logs-bank-*`

**Discover query (Lucene):**

```text
kubernetes.container_name: transfer-service AND event:(transfer_success OR transfer_pending OR transfer_rejected OR transfer_cancelled OR transfer_expired)
```

Nếu chưa có field `event` (chưa parser JSON):

```text
kubernetes.container_name: transfer-service AND log:(*transfer_success* OR *transfer_pending* OR *transfer_rejected* OR *"event":"transfer_*"*)
```

| Visualization | Cấu hình |
|---------------|----------|
| **Metric** — Thành công | Filter `event:transfer_success` → Count |
| **Metric** — Pending | `event:transfer_pending` |
| **Metric** — Thất bại | `event:transfer_rejected` |
| **Metric** — Hủy / hết hạn | `event:(transfer_cancelled OR transfer_expired)` |
| **Pie** — Theo `txn_type` | Split slices: Terms `txn_type.keyword` (top 10), filter transfer_success |
| **Histogram** — Theo thời gian | Vertical axis Count; breakdown Terms `event.keyword` |

### B. Banking — MERCHANT_PAY / shop (NOLI)

```text
kubernetes.container_name: transfer-service AND (event:transfer_success OR log:*MERCHANT_PAY* OR log:*NOLI-*)
```

Metric + table: Terms `note.keyword` hoặc search `log:NOLI-`.

Shop-bridge:

```text
kubernetes.container_name: shop-bridge AND event:(shop_order_seen OR payment_emitted)
```

### C. Shop — Đơn hàng & thanh toán

**Data view:** `logs-shop-*`

```text
event:(order_created OR order_payment_applied OR payment_received)
```

| Panel | Filter / field |
|-------|----------------|
| Đơn mới (chờ CK) | `event:order_created` |
| Đã thanh toán | `event:order_payment_applied AND outcome:paid` |
| Lệch tiền | `event:order_payment_applied AND status:amount_mismatch` |
| Payment worker | `event:payment_received` |
| Histogram đơn/paid | Histogram; series filter order_created vs order_payment_applied |

### D. Lỗi hệ thống (cả 2 index)

```text
(log:*error* OR log:*ERROR* OR log:*failed* OR log:*exception*) AND NOT log:*GET\ /health*
```

---

## 4. Dashboard gợi ý — bố cục

**Dashboard 1: NPD Banking — Transfers**

```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│  SUCCESS    │   PENDING   │  REJECTED   │ EXPIRED/CXL │
├─────────────┴─────────────┴─────────────┴─────────────┤
│     Histogram: transfer events / 5m                    │
├──────────────────────────┬────────────────────────────┤
│  Pie: txn_type           │  Table: log (last 50)      │
└──────────────────────────┴────────────────────────────┘
```

**Dashboard 2: NPD Shop — Orders & Payments**

```
┌──────────────┬──────────────┬──────────────┐
│ order_created│ payment_paid │ pay_received │
├──────────────┴──────────────┴──────────────┤
│  Histogram orders vs payments               │
├────────────────────────────────────────────┤
│  Table: transfer_ref, order_code, amount    │
└────────────────────────────────────────────┘
```

**Dashboard 3: E2E shop-buy (bank + shop)**

- Panel 1 (bank): `event:transfer_success AND txn_type:MERCHANT_PAY`
- Panel 2 (bank): `event:payment_emitted`
- Panel 3 (shop): `event:order_payment_applied AND outcome:paid`

Cùng time range 15m–1h khi chạy cron `job_shop_buy.py`.

---

## 5. Verify sau deploy

```bash
# Có index?
oc -n logging exec sts/npd-logs-master -- curl -sS 'http://127.0.0.1:9200/_cat/indices/logs-*?v'

# Sample document có field event?
oc -n logging exec sts/npd-logs-master -- curl -sS \
  'http://127.0.0.1:9200/logs-bank-*/_search?size=1&q=event:transfer_success' | head -c 800
```

Tạo traffic: ecosystem shop-buy hoặc checkout tay → refresh Dashboard.

---

## 6. Troubleshoot

| Triệu chứng | Xử lý |
|-------------|--------|
| Không có field `event` | Sync Fluent Bit parser; log phải là JSON (`LOG_TRANSFER_JSON` / `LOG_BUSINESS_JSON`) |
| Dashboard trống | Kiểm tra time picker (Last 24 hours); index `logs-bank-YYYY.MM.DD` tồn tại |
| Chỉ thấy GET /health | Rebuild image có `silence_http_probe_logs`; bật JSON business logs |
| shop-bridge không log | Rebuild shop-bridge; có traffic Kafka `orders.events` |

Chi tiết stack logging: [`../DEPLOY.md`](../DEPLOY.md).
