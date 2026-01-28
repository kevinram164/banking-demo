# SLO & Alerting Notes (Phase 5)

Mục tiêu: định nghĩa một vài **SLO đơn giản** dựa trên stack Phase 3 (Prometheus + Grafana) và gợi ý alert rule cơ bản.

## 1. SLO gợi ý cho banking-demo

### 1.1. Availability

- **SLO**: 99% request không trả về 5xx (trong 30 ngày).

Metric: `http_requests_total{job="auth-service"}` (và các service khác).

Error rate (ví dụ cho auth):

```promql
sum(rate(http_requests_total{job="auth-service",status=~"5.."}[5m]))
/ ignoring(status)
sum(rate(http_requests_total{job="auth-service"}[5m]))
```

### 1.2. Latency

- **SLO**: P95 latency < 300ms (trong 30 ngày) cho các API chính.

Metric: `http_request_duration_seconds_bucket` (đã được common lib export).

Ví dụ P95:

```promql
histogram_quantile(
  0.95,
  sum(rate(http_request_duration_seconds_bucket[5m]))
  by (le)
)
```

## 2. Alert rule ví dụ (Prometheus)

Trong Phase 3 bạn có thể thêm vào Prometheus rule (hoặc chỉ để làm tài liệu):

```yaml
groups:
  - name: banking-slo
    rules:
      - alert: HighErrorRateAuth
        expr: |
          (
            sum(rate(http_requests_total{job="auth-service",status=~"5.."}[5m]))
            / ignoring(status)
            sum(rate(http_requests_total{job="auth-service"}[5m]))
          ) > 0.05
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High error rate on auth-service"
          description: "5xx ratio > 5% for more than 10 minutes."

      - alert: HighLatencyP95
        expr: |
          histogram_quantile(
            0.95,
            sum(rate(http_request_duration_seconds_bucket[5m]))
            by (le)
          ) > 0.3
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High p95 latency"
          description: "p95 latency > 300ms for more than 10 minutes."
```

## 3. Chaos idea (dùng để kể chuyện)

- Tắt pod Postgres (StatefulSet) trong vài phút:
  - Quan sát:
    - error rate tăng (5xx)
    - KEDA scale (nếu metrics bên trong vẫn thu thập được)
    - log + traces trong Grafana/Tempo
- Tắt Kong pod:
  - Lưu lượng bị chặn ở gateway, service core vẫn healthy.

Bạn có thể dùng những kịch bản này để demo cách:

- phát hiện sự cố (alert)
- điều tra (dashboard, log, trace)
- rollback/redeploy (Helm/ArgoCD)

