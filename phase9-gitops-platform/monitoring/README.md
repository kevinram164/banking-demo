# NPD Monitoring (OCP)

Hướng dẫn đầy đủ từng bước (đọc file này trước khi apply):

**→ [DEPLOY.md](./DEPLOY.md)** — kiến trúc, checklist, UWM, ServiceMonitor, alert Telegram, Grafana folder NPD + **NPD OCP Infra**, troubleshooting.

Node/disk/etcd: [docs/ocp-infra/](docs/ocp-infra/).

Tóm tắt:

| Mục | Đích |
|-----|------|
| Metrics UI | https://grafana-aiops-observability.apps.ocp01.npd.co → folder **NPD** (app) / **NPD OCP Infra** (node/disk/etcd) |
| Logs | https://logs-platform.apps.ocp01.npd.co (OpenSearch — tách riêng) |
| Alert | OpenShift Alertmanager → Telegram |
