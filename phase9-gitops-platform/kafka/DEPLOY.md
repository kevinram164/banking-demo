# Triển khai Kafka (Strimzi) từng bước — lab OCP NPD

Platform dùng chung (banking + npd-shop). Helm + ArgoCD.  
Storage: **nfs-csi 20Gi**, RAM **~4Gi**, retention **7 ngày**.

---

## Trả lời nhanh: Coroot / Instana?

| Công cụ | Sau khi Kafka lên | Đã “đủ” chưa? |
|---------|-------------------|---------------|
| **Kafka UI** | Topics, messages, consumer groups | Có — UI riêng |
| **Coroot** | Thấy **pod/ns `kafka`**, CPU/RAM, TCP tới bootstrap (eBPF) | **Một phần** — map hạ tầng + traffic, chưa phải Kafka lag/ISR chuyên sâu |
| **Instana** | Thấy **pod K8s**; khi shop/banking produce/consume + OTEL → span `messaging.system=kafka` | **Một phần** — APM từ app; broker JMX/Exporter **chưa** gắn sensor Instana |

Chart đã bật `kafkaExporter` + JMX Prometheus config — metric có trong cluster, nhưng **chưa** cấu hình Instana Kafka sensor / Prometheus scrape vào Coroot cho lag/ISR.  
Muốn sâu hơn = bước sau (scrape `*-kafka-exporter` / bật Instana Kafka).

---

## Checklist tổng

| # | Việc | Xong khi |
|---|------|----------|
| 0 | Code trên GitHub nhánh GitOps | `dev-ocp` (hoặc nhánh `infra-app-of-apps` đang track) có folder kafka |
| 1 | AppProject | `banking-platform` có ns `kafka` + helm repo Strimzi/Kafbat |
| 2 | `infra-strimzi` | Operator Running + CRD `kafkas.kafka.strimzi.io` |
| 3 | `infra-kafka` | `Kafka/npd-kafka` **Ready**, 3 broker pod |
| 4 | Topics | `orders.events`, `payments.events` Ready |
| 5 | `infra-kafka-ui` + Route | Mở được UI |
| 6 | (Tuỳ chọn) Shop `values-kafka` | Pod order/payment có `KAFKA_BOOTSTRAP` |

**Vault:** lab plain `:9092` → **không cần** secret Kafka trên Vault.

---

## Bước 0 — Push code

Máy dev:

```powershell
cd D:\Tai-lieu\LPI-DOCKER-K8S\OCP\banking-demo
git status
git checkout dev-ocp   # hoặc nhánh Argo đang dùng
git add phase9-gitops-platform/kafka phase9-gitops-platform/gitops-platform/applications/infra phase9-gitops-platform/gitops-platform/project.yaml phase9-gitops-platform/environments/dev-ocp/ocp-values/routes
git commit -m "feat(platform): strimzi kafka + kafka-ui helm/argocd"
git push
```

> **Quan trọng:** xem `infra-app-of-apps` đang `targetRevision` nào (`main` hay `dev-ocp`). Code Kafka phải nằm đúng nhánh đó.

```bash
oc -n argocd get application infra-app-of-apps -o jsonpath='{.spec.source.targetRevision}{"\n"}'
```

Nếu app-of-apps = `main` mà bạn push `dev-ocp` → đổi Application sang `dev-ocp` hoặc merge vào `main`.

---

## Bước 1 — AppProject

```bash
oc apply -f phase9-gitops-platform/gitops-platform/project.yaml -n argocd
oc -n argocd get appproject banking-platform -o yaml | grep -E 'kafka|strimzi|kafbat'
```

Cần thấy destination `kafka` và source repo `strimzi.io/charts`, `kafbat.github.io/helm-charts`.

---

## Bước 2 — Sync infra apps

ArgoCD UI → **infra-app-of-apps** → **Refresh** / **Hard Refresh**.

Hoặc:

```bash
# Tạo/cập nhật 3 app (nếu app-of-apps chưa kéo)
oc apply -f phase9-gitops-platform/gitops-platform/applications/infra/strimzi-operator.yaml -n argocd
oc apply -f phase9-gitops-platform/gitops-platform/applications/infra/kafka.yaml -n argocd
oc apply -f phase9-gitops-platform/gitops-platform/applications/infra/kafka-ui.yaml -n argocd
```

### 2.1 Đợi Operator

```bash
oc -n argocd get application infra-strimzi
oc -n kafka get deploy,pod
oc get crd | grep kafka.strimzi.io
```

**OK khi:** CSV/deploy strimzi Running, có CRD `kafkas.kafka.strimzi.io`, `kafkanodepools…`, `kafkatopics…`.

Lỗi thường gặp:

| Lỗi | Xử lý |
|-----|--------|
| Helm repo denied | AppProject thiếu `https://strimzi.io/charts/` |
| Chart version không resolve | Đổi `targetRevision` chart trong `strimzi-operator.yaml` (vd `0.44.0`) cho khớp catalog |

### 2.2 Đợi Kafka cluster

```bash
oc -n argocd get application infra-kafka
oc -n kafka get kafka npd-kafka -o wide
oc -n kafka get kafkanodepool
oc -n kafka get pod -l strimzi.io/cluster=npd-kafka -o wide
oc -n kafka get pvc
```

**OK khi:**

```text
NAME        READY
npd-kafka   True
```

3 pod dual-role (hoặc broker) Running trên **3 worker khác nhau** (anti-affinity).  
PVC `…` Bound với `nfs-csi`, size 20Gi.

Lỗi thường gặp:

| Lỗi | Xử lý |
|-----|--------|
| PVC Pending | `oc get sc nfs-csi` — SC phải tồn tại |
| Pod Pending AntiAffinity | Cluster cần ≥ 3 node schedulable |
| CRD not found | `infra-strimzi` chưa Ready — đợi / sync lại |
| NotReady | `oc -n kafka describe kafka npd-kafka` + logs operator |

### 2.3 Topics

```bash
oc -n kafka get kafkatopic
# orders.events, payments.events → Ready
```

### 2.4 Kafka UI + Route

```bash
oc -n argocd get application infra-kafka-ui
oc -n kafka get svc,pod -l app.kubernetes.io/name=kafka-ui
# Route (platform-routes hoặc apply tay):
oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/routes/kafka-ui-route.yaml
oc -n kafka get route kafka-ui-platform
```

Mở: **https://kafka-ui-platform.apps.ocp01.npd.co**  
Chọn cluster `npd-kafka` → thấy 2 topics.

---

## Bước 3 — Kiểm tra bootstrap

```bash
oc -n kafka get svc | grep bootstrap
# npd-kafka-kafka-bootstrap   9092/TCP, 9093/TCP
```

Lab (plain):

```text
npd-kafka-kafka-bootstrap.kafka.svc.cluster.local:9092
```

Smoke từ pod tạm:

```bash
oc -n kafka run kafkacat --rm -it --restart=Never \
  --image=docker.io/confluentinc/cp-kafkacat:7.6.0 -- \
  kafkacat -b npd-kafka-kafka-bootstrap:9092 -L
```

---

## Bước 4 — Nối npd-shop (sau khi Kafka Ready)

1. File đã có: `npd-shop/gitops/values-kafka.yaml`
2. Uncomment trong `npd-shop/deploy/argocd/npd-shop.yaml`:

```yaml
valueFiles:
  - values.yaml
  - ../../gitops/values-images.yaml
  - ../../gitops/values-observability.yaml
  - ../../gitops/values-kafka.yaml
```

3. Push repo `npd-shop` + sync Argo app `npd-shop`
4. Kiểm tra:

```bash
oc -n npd-shop set env deployment/order-service --list | grep KAFKA
oc -n npd-shop logs deploy/payment-worker --tail=30
# Kỳ vọng: Kafka consumer started  HOẶC  publish khi tạo order
```

---

## Bước 5 — Monitor (lab)

### A. Kafka UI (chi tiết topic/message)
https://kafka-ui-platform.apps.ocp01.npd.co

### B. Coroot
1. Mở Coroot UI (Route coroot lab)
2. Filter namespace **`kafka`**
3. Kỳ vọng: pod brokers, CPU/mem, kết nối TCP từ `npd-shop` / `npd-banking` khi có traffic

### C. Instana
1. Infrastructure → Kubernetes → ns **`kafka`** → pod brokers
2. APM: sau khi shop/banking gửi/nhận message + OTEL → service map có cạnh messaging
3. **Chưa có:** dashboard Kafka broker (ISR, under-replicated) kiểu Instana Kafka sensor — cần cấu hình thêm

---

## Bước 6 (tuỳ chọn) — Lab gần prod: TLS + SCRAM

Trong `infra-kafka` Application, bật:

```yaml
valueFiles:
  - values.yaml
  - values-prod.yaml
```

Sync lại → plain tắt, chỉ `:9093` + SCRAM.  
Lúc đó mới cần đưa password `KafkaUser` vào Vault/ESO cho shop & banking.

---

## Sơ đồ thứ tự

```text
[0] git push (đúng nhánh Argo)
[1] AppProject
[2] infra-strimzi     ──► CRD + operator
[3] infra-kafka       ──► 3 brokers Ready + topics
[4] infra-kafka-ui + Route
[5] (optional) values-kafka trên npd-shop
[6] Coroot ns=kafka · Instana pods · UI topics
```

---

## Rollback nhanh (lab)

```bash
oc -n argocd delete application infra-kafka-ui infra-kafka --wait=false
# Giữ operator nếu muốn
oc -n kafka delete kafka npd-kafka --wait=false
oc -n kafka delete pvc -l strimzi.io/cluster=npd-kafka
```
