# Observability — Coroot + OpenTelemetry + Linkerd (k3d lab)

Stack thống nhất cho **metrics, logs, traces** và **service mesh** trên nhánh `dev-k3d`.

## Kiến trúc

```text
Banking pods (ns banking, Linkerd sidecar)
    │ OTLP gRPC :4317
    ▼
OpenTelemetry Collector (ns observability)
    │ OTLP → Coroot
    ▼
Coroot CE (UI + ClickHouse + eBPF node-agent)
    ├── Metrics (eBPF + OTLP)
    ├── Logs (OTLP)
    └── Traces (OTLP gRPC/HTTP)

Linkerd (ns linkerd) — mTLS mesh, Viz dashboard
```

| Thành phần | Namespace | Domain UI |
|------------|-----------|-----------|
| **Coroot** | `observability` | https://coroot-npd.co |
| **OTEL Collector** | `observability` | — (internal) |
| **Linkerd Viz** | `linkerd-viz` | https://linkerd-npd.co |

## ArgoCD apply (Giai đoạn 2b — sau platform, trước infra)

```bash
# Linkerd: cert tĩnh trong Git (certs/k3d-lab/) — không cần script trước sync

# 2. Sync observability apps
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/applications/observability-app-of-apps.yaml -n argocd
```

Thứ tự sync wave:

| Wave | App |
|------|-----|
| 0 | coroot-operator, linkerd-crds, linkerd-identity-bootstrap |
| 1 | otel-collector, linkerd-control-plane |
| 2 | coroot-ce, linkerd-viz |

## Nginx + Ingress (WSL2)

```bash
sudo cp k3d/nginx-coroot-npd.co.conf /etc/nginx/conf.d/
sudo cp k3d/nginx-linkerd-npd.co.conf /etc/nginx/conf.d/
kubectl apply -f k3d/coroot-ingress.yaml
kubectl apply -f k3d/linkerd-viz-ingress.yaml
sudo nginx -t && sudo systemctl reload nginx
```

Windows `hosts`:

```text
127.0.0.1   coroot-npd.co
127.0.0.1   linkerd-npd.co
```

## Banking app instrumentation

`gitops/values-observability.yaml` được merge vào mọi banking Helm app:

- `OTEL_EXPORTER_OTLP_ENDPOINT` → `opentelemetry-collector.observability:4317`
- Namespace `banking` annotation `linkerd.io/inject: enabled`

Sau khi deploy Linkerd, **restart banking pods** để inject sidecar:

```bash
kubectl rollout restart deployment -n banking
linkerd check
linkerd viz tap deploy/auth-service -n banking
```

## Coroot vs Phase 3 (Grafana/Loki/Tempo)

| | Phase 3 | Phase 9 (k3d) |
|--|---------|---------------|
| Metrics | Prometheus | Coroot + eBPF |
| Logs | Loki + Promtail | Coroot OTLP |
| Traces | Tempo + OTEL | Coroot OTLP |
| UI | Grafana | Coroot |
| Mesh | — | Linkerd |

Phase 3 vẫn giữ trong repo cho cluster production-like; k3d lab dùng Coroot stack.

## RAM khuyến nghị

Coroot + ClickHouse + Linkerd cần thêm **~4–6 GB RAM**. Tổng lab full stack: **≥ 24 GB** WSL2.

## Files

| File | Mục đích |
|------|----------|
| `values-coroot-ce-k3d.yaml` | Coroot CE, local-path storage |
| `values-otel-collector-k3d.yaml` | OTLP gateway → Coroot |
| `values-linkerd-k3d.yaml` | Linkerd k3d (cniEnabled=false) |
| `gitops/values-observability.yaml` | OTEL env + mesh inject cho banking |
| `scripts/generate-linkerd-certs.sh` | Trust anchor + issuer secret |
