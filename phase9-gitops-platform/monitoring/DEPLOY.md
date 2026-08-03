# Hướng dẫn chi tiết — Monitor NPD (Grafana + Alert Telegram)

Tài liệu này mô tả **toàn bộ** những gì cần làm để:

1. Xem dashboard metrics (banking, shop, infra, node OCP) trên Grafana AIOps  
2. Cảnh báo qua kênh **Telegram** khi pod/node/infra lỗi  

Đọc từ trên xuống, làm tuần tự. Mỗi bước có **kiểm tra** — xong mới sang bước sau.

---

## 0. Bức tranh tổng thể (đọc trước khi làm)

```text
App/Infra pods
   │  /metrics  (hoặc exporter sidecar)
   ▼
ServiceMonitor  ──►  OpenShift User Workload Monitoring (Prometheus)
                              │
Node / cluster metrics ◄──────┤  (đã có sẵn từ openshift-monitoring)
                              ▼
                         Thanos Querier
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
     Grafana AIOps                    Alertmanager (OCP)
     folder "NPD"                            │
                                    ┌────────┴────────┐
                                    ▼                 ▼
                               Telegram          Incident API (AIOps)
```

| Việc | Công cụ | Không dùng |
|------|---------|------------|
| **Metrics + dashboard** | Grafana AIOps + OCP Prometheus | Không cài thêm kube-prometheus-stack |
| **Log** | OpenSearch `logs-platform…` | Không nhầm với metrics |
| **Alert chat** | Alertmanager → Telegram | |

**Hai repo liên quan:**

| Repo | Việc |
|------|------|
| `banking-demo` (nhánh `dev-ocp` / `main` tùy Argo) | ServiceMonitor, PrometheusRule, Alertmanager Telegram, UWM config |
| `Open-Source-AIOps-Platform` | Grafana chart + 4 dashboard JSON folder **NPD** |

**Máy làm việc:** bastion có `oc` + quyền **cluster-admin** (bước UWM + node alerts + Secret platform).

---

## 1. Checklist nhanh

- [ ] Bước A — Bật User Workload Monitoring  
- [ ] Bước B — Apply ServiceMonitor (scrape targets)  
- [ ] Bước C — Apply PrometheusRule (định nghĩa alert)  
- [ ] Bước D — Push/sync Grafana AIOps (dashboard NPD)  
- [ ] Bước E — Tạo Telegram bot + Secret + AlertmanagerConfig  
- [ ] Bước F — Test dashboard + test alert Telegram  

---

## 2. Các thành phần mới (giải thích từng cái)

### 2.1 User Workload Monitoring (UWM)

OpenShift mặc định chỉ scrape hệ thống (`openshift-*`).  
App user (`npd-banking`, `redis`, …) cần bật **UWM** thì `ServiceMonitor` / `PrometheusRule` trong ns user mới có hiệu lực.

File: `monitoring/manifests/uwm/user-workload-monitoring-config.yaml`

- `enableUserWorkload: true`  
- `enableUserAlertmanagerConfig: true` (để Telegram config trong ns user được Alertmanager đọc)

### 2.2 ServiceMonitor

Bảo Prometheus: “scrape URL nào, bao lâu một lần”.

| File | Namespace đích |
|------|----------------|
| `servicemonitors/banking.yaml` | `npd-banking` |
| `servicemonitors/shop.yaml` | `npd-shop` |
| `servicemonitors/infra.yaml` | `redis`, `postgres`, `kong`, `kafka`, `rabbit` |

Nếu **label Service** trên cluster khác với manifest → scrape fail → phải sửa `matchLabels` (xem mục Troubleshooting).

### 2.3 PrometheusRule

Định nghĩa điều kiện alert (PromQL + `for: 5m` …).

| File | Ý nghĩa |
|------|---------|
| `prometheusrules/banking.yaml` | Pod banking unavailable / restart / CPU cao |
| `prometheusrules/shop.yaml` | Tương tự shop |
| `prometheusrules/infra.yaml` | Postgres/Redis/Kong/Kafka/Rabbit down, Kafka lag |
| `prometheusrules/nodes.yaml` | Node NotReady, CPU/mem/disk (ns `openshift-monitoring`) |

### 2.4 AlertmanagerConfig + Secret Telegram

Khi alert **firing**, Alertmanager gửi tin nhắn Telegram.

| File | Namespace |
|------|-----------|
| `alertmanager/telegram-banking.yaml` | `npd-banking` |
| `alertmanager/telegram-shop.yaml` | `npd-shop` |
| `alertmanager/telegram-platform.yaml` | `openshift-monitoring` (node alerts) |
| `alertmanager/secret.example.yaml` | Mẫu — **không** commit token thật |

Cần Secret tên `alertmanager-telegram` key `bot-token` trong **cùng namespace** với AlertmanagerConfig.

### 2.5 Grafana dashboards (repo AIOps)

Dashboard **chi tiết** port từ Phase 3 (`banking-demo/phase3-monitoring-keda/helm-monitoring/`):

| Dashboard (folder **NPD**) | Nguồn Phase 3 | Metrics app |
|----------------------------|---------------|-------------|
| **NPD Banking Services** | `grafana-dashboard-banking-services-phase8.yaml` | RPS, p95, 5xx, transfer success |
| **NPD Shop Services** | (clone pattern Phase 8 → ns `npd-shop`) | HTTP shop |
| **NPD Kong Gateway** | `grafana-dashboard-kong.yaml` | Kong nginx/datastore |
| **NPD RabbitMQ** | `grafana-dashboard-rabbitmq.yaml` | queue/consumer (cần exporter) |
| NPD Infra | overview scrape + Kafka lag | |
| NPD OCP Nodes | CPU/mem/disk nodes | |

Regenerate từ Phase 3 (sau khi sửa dashboard gốc):

```bash
cd /path/to/OCP   # workspace có banking-demo + Open-Source-AIOps-Platform
python banking-demo/phase9-gitops-platform/monitoring/scripts/port_phase3_dashboards.py
```

Query đã gắn `namespace=npd-banking|npd-shop|…` và nới `job=~` cho ServiceMonitor OCP.

---

## 3. Chuẩn bị trước

```bash
# Đứng đúng clone
cd /path/to/banking-demo   # hoặc OCP/banking-demo trên máy bạn

# Context cluster đúng
oc whoami
oc project   # hoặc oc config current-context

# Quyền — cần cluster-admin cho UWM + openshift-monitoring
oc auth can-i create configmap -n openshift-monitoring
```

Clone thêm (nếu chưa):

```bash
# Repo Grafana AIOps
cd /path/to/Open-Source-AIOps-Platform
git status
git pull
```

---

## 4. Bước A — Bật User Workload Monitoring

Ns `openshift-user-workload-monitoring` **đã có** (Console thấy được) nhưng **trống pod** vì CM thiếu `enableUserWorkload`.

`ConfigMap/cluster-monitoring-config` đang do Argo **`aiops-alertmanager-platform`** quản lý — chỉ có `alertmanagerMain`, **không** có `enableUserWorkload` → UWM không bao giờ start.

### Cách nhanh (bastion) — làm ngay

```bash
oc -n openshift-monitoring edit cm cluster-monitoring-config
```

Đổi `data.config.yaml` thành:

```yaml
enableUserWorkload: true
alertmanagerMain:
  enableUserAlertmanagerConfig: true
```

Save → đợi 1–3 phút:

```bash
oc -n openshift-user-workload-monitoring get pods -w
# prometheus-operator, prometheus-user-workload-*, thanos-ruler-user-workload-*
```

### Cách bền (tránh Argo revert)

Đã sửa Git AIOps: `integrations/alertmanager/overlays/openshift-monitoring/cluster-monitoring-config.yaml`  
→ push + sync app **`aiops-alertmanager-platform`**.

**Không** `oc apply` lại file UWM từ banking-demo lên `cluster-monitoring-config` (Argo sẽ ghi đè mất `enableUserWorkload` nếu Git chưa cập nhật).

Chỉ apply tinh chỉnh retention (tuỳ chọn):

```bash
oc apply -f phase9-gitops-platform/monitoring/manifests/uwm/user-workload-monitoring-config.yaml
```

---

## 5. Bước B — ServiceMonitor (scrape metrics)

```bash
cd banking-demo
oc apply -k phase9-gitops-platform/monitoring/manifests/servicemonitors
```

### Kiểm tra object đã tạo

```bash
oc get servicemonitor -A | grep -E 'banking|shop|redis|postgres|kong|kafka|rabbit|NAME'
```

### Kiểm tra scrape có target không

Cách 1 — OpenShift Console: **Observe → Targets** (User workload) — tìm job liên quan `npd-banking` / `redis` …

Cách 2 — query Thanos (sau khi Grafana OK) hoặc:

```bash
# Label Service thực tế (để sửa matchLabels nếu up=0)
oc -n npd-banking get svc --show-labels
oc -n npd-shop get svc --show-labels
oc -n redis get svc
oc -n postgres get svc | head
oc -n kong get svc
oc -n kafka get svc | grep -iE 'export|metric|NAME'
oc -n rabbit get svc
```

**Nếu ServiceMonitor không khớp label** → sửa file YAML `matchLabels` / `port` cho đúng, `oc apply` lại.

> **RabbitMQ:** lab standalone có thể **chưa** có port metrics → target `down` là bình thường cho đến khi bật plugin prometheus.

---

## 6. Bước C — PrometheusRule (cảnh báo)

```bash
cd banking-demo
oc apply -k phase9-gitops-platform/monitoring/manifests/prometheusrules
oc apply -f phase9-gitops-platform/monitoring/manifests/prometheusrules/nodes.yaml
```

### Kiểm tra

```bash
oc get prometheusrule -A | grep npd
# npd-banking-alerts, npd-shop-alerts, npd-infra-*, npd-ocp-node-alerts
```

Alert **chưa** bắn Telegram cho đến khi xong bước E (AlertmanagerConfig + bot).

---

## 7. Bước D — Dashboard Grafana (repo AIOps)

### 7.1 Commit / push (nếu chưa lên remote)

Trên máy có thay đổi AIOps:

```bash
cd Open-Source-AIOps-Platform
git add charts/grafana/
git status
git commit -m "feat(grafana): NPD dashboards + Thanos RBAC token"
git push origin main   # hoặc nhánh Argo đang track
```

### 7.2 Sync Argo

- Argo CD → app **`grafana`** (ns `aiops-observability`) → **Sync**  
- Hoặc chờ auto-sync nếu đã bật

```bash
oc -n aiops-observability get deploy grafana
oc -n aiops-observability get secret grafana-thanos-token
oc -n aiops-observability get cm | grep dashboard-npd
oc -n aiops-observability rollout restart deploy/grafana
oc -n aiops-observability rollout status deploy/grafana
```

### 7.3 Mở UI

1. https://grafana-aiops-observability.apps.ocp01.npd.co  
2. Login (Vault/secret `grafana-admin`)  
3. Menu **Dashboards** → folder **NPD**  
4. Ưu tiên mở **NPD Banking Services** (RPS / p95 / transfer — giống Phase 3)  
5. Góc trên chọn datasource **Prometheus** (nếu panel hỏi)

### Kiểm tra

- Panel có số liệu (không toàn “No data”) → OK.  
- “No data” trên banking nhưng **Nodes** có data → UWM/ServiceMonitor banking chưa khớp; node vẫn lấy từ platform Prometheus.  
- Cả hai đều No data → Thanos token / RBAC (xem Troubleshooting).

---

## 8. Bước E — Telegram

### 8.1 Tạo bot

1. Telegram → chat **@BotFather** → `/newbot` → lấy **token** dạng `123456:AA...`  
2. Tạo **channel** hoặc dùng group; add bot làm admin (channel) / member (group)  
3. Lấy **chat id**:
   - Channel public: thường `-100xxxxxxxxxx`  
   - Cách nhanh: gửi message vào channel, mở  
     `https://api.telegram.org/bot<TOKEN>/getUpdates`  
     → tìm `"chat":{"id":-100...}`

### 8.2 Sửa `chatID` trong YAML

Mở 3 file, đổi `-1000000000000` thành chat id thật:

- `monitoring/manifests/alertmanager/telegram-banking.yaml`  
- `…/telegram-shop.yaml`  
- `…/telegram-platform.yaml`  

Field: `chatID: -100xxxxxxxxxx` (số nguyên, **không** quote nếu CRD yêu cầu int).

### 8.3 Tạo Secret bot token

```bash
export BOT='123456:AA...'   # token thật

for ns in npd-banking npd-shop openshift-monitoring; do
  oc -n "$ns" create secret generic alertmanager-telegram \
    --from-literal=bot-token="$BOT" \
    --dry-run=client -o yaml | oc apply -f -
done

# (Tuỳ chọn) infra ns nếu sau này gắn AlertmanagerConfig riêng
for ns in postgres kafka kong rabbit; do
  oc -n "$ns" create secret generic alertmanager-telegram \
    --from-literal=bot-token="$BOT" \
    --dry-run=client -o yaml | oc apply -f -
done
```

### 8.4 Apply AlertmanagerConfig

```bash
cd banking-demo
oc apply -f phase9-gitops-platform/monitoring/manifests/alertmanager/telegram-banking.yaml
oc apply -f phase9-gitops-platform/monitoring/manifests/alertmanager/telegram-shop.yaml
oc apply -f phase9-gitops-platform/monitoring/manifests/alertmanager/telegram-platform.yaml
```

### Kiểm tra

```bash
oc get alertmanagerconfig -A | grep -E 'npd-telegram|aiops'
oc -n openshift-monitoring get alertmanager main -o yaml | grep -A10 alertmanagerConfig
```

Phải có `enableUserAlertmanagerConfig: true` (bước A).

---

## 9. Bước F — Test end-to-end

### 9.1 Dashboard

- Grafana → NPD Banking: có pod count / CPU  
- NPD OCP Nodes: có CPU% các worker  

### 9.2 Alert → Telegram

```bash
# Cảnh báo: lab tạm scale 0
oc -n npd-banking scale deploy/api-producer --replicas=0

# Đợi ~5–10 phút (rule for: 5m + groupWait)
# Kỳ vọng: tin nhắn Telegram BankingPodNotReady / tương tự

# Restore
oc -n npd-banking scale deploy/api-producer --replicas=1
```

Xem Alertmanager:

```bash
oc logs -n openshift-monitoring -l app.kubernetes.io/name=alertmanager --tail=80 | grep -iE 'telegram|error|notify'
```

---

## 10. Troubleshooting

| Hiện tượng | Việc kiểm |
|------------|-----------|
| Không có pod `openshift-user-workload-monitoring` | CM `enableUserWorkload` chưa có / operator chưa reconcile |
| ServiceMonitor có nhưng Grafana No data (app) | Sai `matchLabels` / sai `port` — so `oc get svc --show-labels`. **Quan trọng:** nếu `count by (endpoint)` ra `endpoint="8080"` (số port) thay vì `/api/...` → thiếu `honorLabels: true` trên ServiceMonitor (label scrape đè label app). |
| Nodes OK, app No data | UWM chưa scrape; kiểm Targets User Workload |
| Grafana toàn No data | Secret `grafana-thanos-token` + ClusterRoleBinding `cluster-monitoring-view` |
| Alert firing nhưng không vào Tele | Sai `chatID`, bot chưa vào channel, Secret sai ns, hoặc `enableUserAlertmanagerConfig` |
| Rabbit `up=0` | Chưa bật metrics plugin — chấp nhận hoặc nâng cấp Rabbit |
| Kafka lag trống | Chưa có pod/Service `*-kafka-exporter` — patch Kafka CR `spec.kafkaExporter` |
| Transfer panel 0% / No data | Cùng bug `honorLabels`; sau fix: `count by (endpoint) (http_requests_total{namespace="npd-banking"})` phải thấy `/api/transfer/transfer` |
---

## 11. Việc không cần làm

- Không cài Prometheus/Grafana thứ hai trong ns `monitoring` (trùng OCP).  
- Không đưa log OpenSearch vào Grafana để “thay” metrics (log = Discover OpenSearch).  
- Không commit bot token vào Git.

---

## 12. Map thư mục (tra cứu)

```text
banking-demo/phase9-gitops-platform/monitoring/
├── DEPLOY.md                          ← file này
├── README.md
├── manifests/
│   ├── uwm/user-workload-monitoring-config.yaml
│   ├── servicemonitors/{banking,shop,infra}.yaml
│   ├── prometheusrules/{banking,shop,infra,nodes}.yaml
│   └── alertmanager/telegram-*.yaml
└── (Argo tùy chọn) ../gitops-platform/applications/monitoring-apps.yaml

Open-Source-AIOps-Platform/
└── charts/grafana/
    ├── dashboards/npd-*.json
    └── templates/{configmaps,all,thanos-rbac}.yaml
```

---

## 13. Thứ tự lệnh tóm tắt (copy-paste)

```bash
# === banking-demo ===
cd banking-demo
oc apply -f phase9-gitops-platform/monitoring/manifests/uwm/user-workload-monitoring-config.yaml
oc -n openshift-user-workload-monitoring get pods   # đợi Running

oc apply -k phase9-gitops-platform/monitoring/manifests/servicemonitors
oc apply -k phase9-gitops-platform/monitoring/manifests/prometheusrules
oc apply -f phase9-gitops-platform/monitoring/manifests/prometheusrules/nodes.yaml

# Telegram: sửa chatID trong YAML trước, rồi:
export BOT='YOUR_BOT_TOKEN'
for ns in npd-banking npd-shop openshift-monitoring; do
  oc -n "$ns" create secret generic alertmanager-telegram \
    --from-literal=bot-token="$BOT" --dry-run=client -o yaml | oc apply -f -
done
oc apply -f phase9-gitops-platform/monitoring/manifests/alertmanager/telegram-banking.yaml
oc apply -f phase9-gitops-platform/monitoring/manifests/alertmanager/telegram-shop.yaml
oc apply -f phase9-gitops-platform/monitoring/manifests/alertmanager/telegram-platform.yaml

# === AIOps Grafana ===
# git push Open-Source-AIOps-Platform → Argo sync grafana → mở folder NPD
```

Xong checklist mục **1** là lab monitor + Telegram đủ dùng. Gặp lỗi ở bước nào, gửi output lệnh **Kiểm tra** của bước đó.
