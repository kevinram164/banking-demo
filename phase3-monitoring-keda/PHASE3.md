# Giai đoạn 3: Monitoring, Logging, Tracing & KEDA (HPA)

Giai đoạn 3 tập trung **observability chuyên sâu** (metrics, logging, tracing) và **autoscaling với KEDA**, kèm **kịch bản test tải** để kiểm chứng KEDA hoạt động đúng.

---

## Mục tiêu

- **Monitoring:** Prometheus (metrics) + Grafana (dashboards). Phase3 triển khai bằng **Helm** (pull chart, sửa values) — xem `helm-monitoring/`.
- **Logging:** Loki + Promtail (Helm). Log pod → Promtail → Loki; Grafana query Loki.
- **Tracing:** OpenTelemetry Collector + Tempo (Helm). App gửi OTLP → Collector → Tempo. (Tempo nhẹ hơn Jaeger, tích hợp tốt với Grafana)
- **KEDA:** Scale các Deployment (auth, account, transfer, notification) theo **Prometheus metrics** (ví dụ `http_requests_total` rate). Không dùng HPA mặc định của K8s.
- **Load test:** Script (k6) tạo tải lên API → tăng RPS → KEDA scale up; dừng tải → scale down. Có hướng dẫn chạy và kiểm tra kết quả.

---

## Sơ đồ luồng

- **Draw.io:** Mở `phase3-flow.drawio` bằng [draw.io](https://app.diagrams.net/) để xem/chỉnh sửa.
- **Mermaid + mô tả:** Xem `PHASE3-FLOW.md`.

---

## Cấu trúc thư mục

```
phase3-monitoring-keda/
├── PHASE3.md                 # File này
├── PHASE3-FLOW.md            # Sơ đồ luồng (Mermaid) + ghi chú
├── METRICS-PERCENTILES.md    # Giải thích P50, P95, P99 và cách dùng trong dashboards/load test
├── phase3-flow.drawio        # Sơ đồ Draw.io
├── helm-monitoring/          # Monitoring + Logging + Tracing (Helm)
│   ├── README.md             # Repos, thứ tự cài, từng chart
│   ├── values-kube-prometheus-stack.yaml  # Prometheus + Grafana
│   ├── values-loki.yaml      # Loki
│   ├── values-promtail.yaml  # Promtail → Loki
│   ├── values-tempo.yaml     # Tempo (tracing backend)
│   └── values-otel-collector.yaml  # OTEL Collector → Tempo
├── keda/
│   ├── README.md             # Cài KEDA, apply ScaledObjects
│   ├── scaledobject-auth.yaml
│   ├── scaledobject-account.yaml
│   ├── scaledobject-transfer.yaml
│   └── scaledobject-notification.yaml
└── load-test/
    ├── README.md             # Cách chạy, kịch bản, đánh giá KEDA
    ├── k6-auth.js            # Load /api/auth (login)
    ├── k6-account.js         # Load /api/account (me, balance)
    ├── k6-transfer.js        # Load /api/transfer
    └── run-scenarios.sh      # Chạy các kịch bản, gợi ý lệnh kiểm tra
```

---

## Điều kiện tiên quyết

1. **Banking app** đã chạy (phase1 hoặc phase2): namespace `banking`, các service có `/metrics` và OTEL (nếu dùng tracing).
2. **Monitoring stack** trong namespace `monitoring`:
   - **Khuyến nghị phase3:** triển khai bằng Helm theo `helm-monitoring/README.md` (Prometheus + Grafana, Loki, Promtail, Tempo, OpenTelemetry Collector). Pull chart, sửa `values-*.yaml`, rồi `helm install/upgrade`.
   - Hoặc dùng `k8s/monitoring` (manifest YAML). Xem `OBSERVABILITY.md` và `k8s/monitoring/`.
3. **KEDA** đã cài trên cluster (xem `keda/README.md`).
4. **k6** cài local hoặc trong container để chạy load test (xem `load-test/README.md`).

---

## Luồng hoạt động (KEDA + load test)

1. **Prometheus** scrape `http_requests_total` từ từng service. KEDA query ví dụ:
   - `sum(rate(http_requests_total{job="auth-service"}[2m]))`
2. **ScaledObject** so sánh giá trị query với **threshold**. Nếu > threshold → tăng replica; nếu < **activationThreshold** (và đủ điều kiện) → giảm replica.
3. **Load test** gửi nhiều request tới `/api/auth`, `/api/account`, `/api/transfer` qua Ingress hoặc port-forward → RPS tăng → KEDA scale up.
4. Dừng load test → RPS giảm → sau cooldown, KEDA scale down.

---

## Thứ tự triển khai (tóm tắt)

```bash
# 1. Monitoring + Logging + Tracing (Helm) — xem helm-monitoring/README.md
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update
kubectl create namespace monitoring
helm upgrade -i kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring -f phase3-monitoring-keda/helm-monitoring/values-kube-prometheus-stack.yaml
helm upgrade -i loki grafana/loki -n monitoring -f phase3-monitoring-keda/helm-monitoring/values-loki.yaml
helm upgrade -i promtail grafana/promtail -n monitoring -f phase3-monitoring-keda/helm-monitoring/values-promtail.yaml
helm upgrade -i tempo grafana/tempo -n monitoring -f phase3-monitoring-keda/helm-monitoring/values-tempo.yaml
helm upgrade -i otel-collector open-telemetry/opentelemetry-collector -n monitoring -f phase3-monitoring-keda/helm-monitoring/values-otel-collector.yaml

# 2. KEDA (operator + CRDs) — xem keda/README.md
helm repo add kedacore https://kedacore.github.io/charts
helm upgrade -i keda kedacore/keda -n keda --create-namespace

# 3. ScaledObjects (sau khi Prometheus đã scrape được metrics)
kubectl apply -f phase3-monitoring-keda/keda/

# 4. Chạy load test và kiểm tra scale
cd phase3-monitoring-keda/load-test && ./run-scenarios.sh
kubectl get hpa -n banking
kubectl get pods -n banking -w
```

(Thay bằng `k8s/monitoring` manifest nếu không dùng Helm — xem `OBSERVABILITY.md`.)

---

## Kiểm chứng KEDA

- Trước load test: `kubectl get pods -n banking` → mỗi deployment 1 replica.
- Trong lúc chạy k6 (RPS cao): `kubectl get pods -n banking` và `kubectl get hpa -n banking` → replicas tăng (tới maxReplicaCount).
- Sau khi dừng k6: đợi vài phút → replicas giảm dần về minReplicaCount.

Chi tiết kịch bản, biến môi trường (BASE_URL, VUs, duration) và các lệnh kiểm tra nằm trong `load-test/README.md` và `keda/README.md`. Chi tiết từng bước cài monitoring (Helm), chỉnh values, và kiểm tra UI nằm trong `helm-monitoring/README.md`.

**Metrics & percentiles:** Xem `METRICS-PERCENTILES.md` để hiểu P50, P95, P99 và cách chúng được dùng trong dashboards và load test.
