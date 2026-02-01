# Metrics và Percentiles (P50, P90, P95, P99)

Tài liệu giải thích **latency percentiles** và cách chúng được dùng trong phase3 (dashboards, load test, SLA).

---

## 1. Percentile là gì?

**Percentile** cho biết **X% request** có thời gian phản hồi **nhỏ hơn hoặc bằng** giá trị đó.

| Percentile | Ý nghĩa | Ví dụ |
|------------|---------|-------|
| **P50** (median) | 50% request ≤ X ms | P50 = 50ms → nửa số request trả về trong ≤50ms |
| **P75** | 75% request ≤ X ms | |
| **P90** | 90% request ≤ X ms | |
| **P95** | 95% request ≤ X ms | P95 = 200ms → 95% request ≤ 200ms, 5% chậm hơn |
| **P99** | 99% request ≤ X ms | |
| **P99.9** | 99.9% request ≤ X ms | "Tail latency" — theo dõi request rất chậm |

---

## 2. Các percentile thường dùng trong monitoring

| Percentile | Khi nào dùng | Ghi chú |
|------------|--------------|---------|
| **P50 (median)** | Trải nghiệm điển hình | Ít bị ảnh hưởng bởi outliers; "đại đa số" user |
| **P95** | SLA, mục tiêu hiệu năng | Cân bằng giữa độ đại diện và độ nhạy; **phổ biến nhất** |
| **P99** | SLA nghiêm ngặt | Theo dõi trải nghiệm tệ nhất của ~1% request |

### Tại sao không chỉ dùng average (trung bình)?

- **Average** dễ bị kéo lên bởi vài request rất chậm (ví dụ timeout 30s).
- **P95** ổn định hơn: 5% request chậm nhất không làm lệch quá nhiều.

---

## 3. Percentile trong Phase3

### 3.1 Grafana Dashboard (Banking Services)

Panel **"P95 Latency by Service"** dùng PromQL:

```
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (job, le))
```

→ Hiển thị **P95** latency theo từng service (auth, account, transfer, notification).

### 3.2 Load test (k6)

Các script k6 đặt threshold:

- **k6-auth.js:** `http_req_duration: ['p(95)<3000']` → 95% request phải < 3s.
- **k6-transfer.js:** `http_req_duration: ['p(95)<5000']` → 95% request phải < 5s.

Nếu P95 vượt threshold → k6 báo lỗi `ERRO[xxxx] thresholds on metrics 'http_req_duration' have been crossed`.

### 3.3 HPA / KEDA

HPA và KEDA scale theo **CPU/Memory** hoặc **Prometheus metrics** (rate), không dùng trực tiếp percentiles. Nhưng khi P95 tăng cao → có thể cần scale thêm replica để giảm tải.

---

## 4. Nên chú ý P nào?

| Mục đích | Percentile nên dùng |
|----------|---------------------|
| SLA / mục tiêu chung | **P95** |
| Điều tra trải nghiệm tệ nhất | **P99** |
| So sánh nhanh trải nghiệm "điển hình" | **P50** |
| Debug tail latency (rất hiếm) | **P99.9** |

**Thực tế:** Ưu tiên theo dõi **P95** cho SLA và alert; thêm **P99** nếu SLA nghiêm ngặt.

---

## 5. Ví dụ minh họa

```
100 request, thời gian phản hồi (ms): 
50, 55, 48, 52, 60, 49, 51, 53, 47, 54, ..., 5000 (1 request timeout)

→ P50 ≈ 52ms   (median)
→ P95 ≈ 55ms   (95% request nhanh; 5% cuối có thể có timeout)
→ P99 ≈ 5000ms (1% chậm nhất)
→ Average bị kéo lên bởi 1 request 5s
```

---

## 6. Tham khảo

- Dashboard Banking Services: `helm-monitoring/dashboards/banking-services.json`
- Load test k6: `load-test/k6-auth.js`, `k6-transfer.js`
- Prometheus histogram: https://prometheus.io/docs/practices/histograms/
