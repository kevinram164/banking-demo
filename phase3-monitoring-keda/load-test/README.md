# Load test — Kịch bản test tải cho KEDA

Dùng **k6** để tạo tải lên API banking (qua Ingress hoặc port-forward). Mục tiêu: tăng RPS → Prometheus scrape `http_requests_total` → KEDA scale up; dừng tải → scale down.

## Yêu cầu

- **k6** cài trên máy chạy test: https://k6.io/docs/getting-started/installation/
- Banking app đang chạy, có thể gọi được API (BASE_URL).

## Biến môi trường

| Biến | Mô tả | Mặc định |
|------|--------|----------|
| `BASE_URL` | Base URL API (Kong hoặc ingress) | `http://localhost:8000` |
| `HOST_HEADER` | Host header (bắt buộc khi gọi bằng IP) | _(trống)_ |
| `VUS` | Số virtual users (song song) | `10` |
| `DURATION` | Thời gian chạy mỗi kịch bản | `2m` |

**Khi gọi bằng IP:** Ingress route theo `Host`. Nếu `BASE_URL=http://10.100.1.100` thì phải set `HOST_HEADER=npd-banking.co` (đúng với `ingress.host` trong phase2) thì mới không bị 404.

Ví dụ:

```bash
export BASE_URL="https://npd-banking.co"
export VUS=20
export DURATION=3m
```

Gọi bằng IP (jump-host, cùng mạng):

```bash
BASE_URL="http://10.100.1.100" HOST_HEADER="npd-banking.co" VUS=20 DURATION=3m k6 run k6-transfer.js
```

## Kịch bản

### 1. `k6-auth.js` — Tải lên Auth service

- Gọi **POST /api/auth/login** (và **POST /api/auth/register** nếu cần tạo user test).
- Tạo nhiều request liên tục → tăng RPS cho `auth-service` → KEDA scale auth.

**Chạy:**

```bash
k6 run --vus 10 --duration 2m k6-auth.js
# hoặc
BASE_URL=https://npd-banking.co VUS=20 DURATION=3m k6 run k6-auth.js
```

### 2. `k6-account.js` — Tải lên Account service

- Login 1 lần lấy session, sau đó gọi **GET /api/account/me** (hoặc **/api/account/balance**) lặp lại.
- Tăng RPS cho `account-service` → KEDA scale account.

### 3. `k6-transfer.js` — Tải lên Transfer (+ Notification)

- Dùng 2 user test, chuyển tiền qua lại **POST /api/transfer/transfer**.
- Tăng RPS cho `transfer-service` (và `notification-service` nếu gọi /notifications).

## Chạy tất cả kịch bản

```bash
./run-scenarios.sh
```

Script sẽ chạy lần lượt auth → account → transfer (hoặc theo thứ tự bạn chỉnh trong file), với `VUS` và `DURATION` từ env.

**Windows:** Dùng Git Bash hoặc WSL để chạy `run-scenarios.sh`. Hoặc chạy từng kịch bản thủ công:

```powershell
k6 run --vus 10 --duration 2m -e BASE_URL=https://npd-banking.co k6-auth.js
```

## Kiểm tra KEDA khi chạy load test

**Trước khi chạy:**

```bash
kubectl get pods -n banking
kubectl get scaledobject -n banking
kubectl get hpa -n banking
```

**Trong lúc chạy k6 (cửa sổ khác):**

```bash
watch -n 5 'kubectl get pods -n banking'
# hoặc
kubectl get pods -n banking -w
```

Kỳ vọng: số replica của `auth-service`, `account-service`, `transfer-service`, `notification-service` tăng (tối đa theo `maxReplicaCount` trong ScaledObject) khi RPS vượt threshold.

**Sau khi dừng k6:**

Đợi vài phút (cooldown 120s). Replicas giảm dần về `minReplicaCount` (1).

## Kiểm chứng KEDA hoạt động chuẩn

1. **Trước load test:** `kubectl get pods -n banking` — mỗi service (auth, account, transfer, notification) 1 pod.
2. **Chạy** `k6 run k6-auth.js` (hoặc `run-scenarios.sh`) với `VUS` đủ lớn (vd. 15–20) và `DURATION` ít nhất 1–2 phút.
3. **Trong lúc chạy:** `kubectl get pods -n banking` — số pod của `auth-service` (và các service tương ứng khi chạy k6-account / k6-transfer) tăng, tối đa `maxReplicaCount` (5 trong ScaledObject).
4. **Dừng k6**, đợi vài phút (cooldown 120s): replicas giảm dần về 1.

Nếu bước 3–4 đúng như trên thì KEDA scale theo Prometheus RPS đúng mong đợi.

## Gợi ý Prometheus

Kiểm tra metric KEDA dùng:

```bash
# Trong Prometheus (hoặc port-forward prometheus:9090)
sum(rate(http_requests_total{job="auth-service"}[2m]))
```

Khi chạy `k6-auth.js` với đủ VUs, giá trị này sẽ tăng; khi dừng, giảm dần.

## User test

Các script dùng user `loadtest1` / `loadtest1` (và `loadtest2` cho transfer). Nếu chưa có, `k6-auth.js` sẽ gọi register trước. Đảm bảo không bị conflict (username unique).
