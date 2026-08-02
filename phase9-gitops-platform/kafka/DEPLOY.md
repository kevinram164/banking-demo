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

> **Quan trọng:** `infra-app-of-apps` phải track **`dev-ocp`** (đã cập nhật trong repo).  
> Nếu Argo vẫn `targetRevision: main` → operator mãi 0.45.0 dù bạn đã push fix trên `dev-ocp`.

```bash
oc -n argocd get application infra-app-of-apps -o jsonpath='{.spec.source.targetRevision}{"\n"}'
oc -n argocd get application infra-strimzi -o jsonpath='{.spec.source.targetRevision}{"\n"}'
# Kỳ vọng: dev-ocp  và  chart 0.46.1
```

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
| Chart version không resolve | Đổi `targetRevision` trong `strimzi-operator.yaml` |
| Operator CrashLoop `emulationMajor` / `UnrecognizedPropertyException` | OCP trả field mới trong `/version`. Đã fix bằng chart **≥0.46.1** + env `STRIMZI_KUBERNETES_VERSION`. Sync lại `infra-strimzi`, xoá pod operator cũ nếu còn. |
| `javaagent-loader … Operation not permitted` | Instana/Java agent inject — **bỏ qua**, không phải nguyên nhân crash |

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

3 pod dual-role Running. Lab: **không** dùng `rack.topologyKey` (worker thường thiếu `topology.kubernetes.io/zone` → Pending). Anti-affinity mặc định là *preferred*.  
PVC `…` Bound với `nfs-csi`, size 20Gi.

#### 2.2a PVC nfs-csi `AccessDeniedException` (meta.properties)

Kafka UID = `1000910000` (ns `kafka`). **nfs-csi thường bỏ qua `fsGroup`** → phải `chown`/`chmod` trên volume.

```bash
# Cho phép pod fix chạy root (lab, tạm)
oc adm policy add-scc-to-user anyuid -z default -n kafka

# Dừng broker (giải phóng PVC nếu RWO)
oc -n kafka patch kafkanodepool dual-role --type=merge -p '{"spec":{"replicas":0}}'
oc -n kafka delete pod -l strimzi.io/cluster=npd-kafka --force --grace-period=0 2>/dev/null
oc -n kafka wait --for=delete pod -l strimzi.io/cluster=npd-kafka --timeout=120s 2>/dev/null || true

# Fix quyền từng data PVC
for PVC in $(oc -n kafka get pvc -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep data); do
  echo "=== fix $PVC ==="
  oc -n kafka delete pod "vol-fix-$PVC" --ignore-not-found --force --grace-period=0
  cat <<EOF | oc -n kafka apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: vol-fix-$PVC
spec:
  restartPolicy: Never
  containers:
  - name: fix
    image: busybox:1.36
    command: ["sh","-c","chown -R 1000910000:1000910000 /data; chmod -R u+rwX,g+rwX /data; ls -la /data"]
    securityContext:
      runAsUser: 0
    volumeMounts:
    - name: d
      mountPath: /data
  volumes:
  - name: d
    persistentVolumeClaim:
      claimName: $PVC
EOF
  oc -n kafka wait --for=jsonpath='{.status.phase}'=Succeeded pod/"vol-fix-$PVC" --timeout=120s
  oc -n kafka logs "vol-fix-$PVC"
  oc -n kafka delete pod "vol-fix-$PVC"
done

# Bật lại 3 broker
oc -n kafka patch kafkanodepool dual-role --type=merge -p '{"spec":{"replicas":3}}'
oc -n kafka get pods -l strimzi.io/cluster=npd-kafka -w
```

Sau đó log không còn `AccessDenied`; `oc -n kafka get kafka npd-kafka` → Ready.

> Cách bền: trên NFS server `chown -R 1000910000:1000910000 <path-export>`, hoặc dùng block CSI. Có thể gỡ SCC: `oc adm policy remove-scc-from-user anyuid -z default -n kafka`.

Lỗi thường gặp:

| Lỗi | Xử lý |
|-----|--------|
| PVC Pending | `oc get sc nfs-csi` — SC phải tồn tại |
| Pod Pending `topology.kubernetes.io/zone` / node affinity | Lab worker thường **không** có label zone. Chart mặc định **tắt rack**. Nếu CR cũ còn rack / pod còn `nodeAffinity zone Exists`: gỡ rack + `oc delete strimzipodset -l strimzi.io/cluster=npd-kafka`, hoặc gắn tạm `oc label node <worker> topology.kubernetes.io/zone=zone-a`. |
| Pod Pending AntiAffinity | Cluster cần ≥ 3 node schedulable; lab dùng preferred anti-affinity |
| CRD not found | `infra-strimzi` chưa Ready — đợi / sync lại |
| NotReady | `oc -n kafka describe kafka npd-kafka` + logs operator |
| Xóa SPS rồi không có pod | `oc -n kafka get kafka,kafkanodepool,strimzipodset` + annotate Kafka để reconcile; xem log operator |
| `AccessDeniedException: .../kafka-log0` | nfs-csi mount root-owned; Kafka UID OCP không ghi được. Xem §2.2a |
| Sync Failed: `--force` cannot be used with `--server-side` | Bỏ tick **Force** khi sync, hoặc bỏ `ServerSideApply` khỏi Application (đã sửa trong `infra/kafka.yaml`). |

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

## Bước 4b — Nối banking (`shop-bridge`)

Luồng: shop `orders.events` → banking **shop-bridge** → `payments.events` → shop payment-worker.

1. Copy SCRAM user + CA vào ns `npd-banking`:

```bash
bash phase9-gitops-platform/environments/dev-ocp/scripts/sync-kafka-client-secrets.sh
oc -n npd-banking get secret npd-banking-kafka-user npd-banking-kafka-cluster-ca
```

2. Build/push image `shop-bridge` (Jenkins `PipelineConfig` đã có service; hoặc Kaniko tay).  
   Tag cập nhật trong `gitops/values-images.yaml` → key `shop-bridge`.

3. Sync Argo `banking-shop-bridge` (app-of-apps banking recurse, hoặc):

```bash
oc apply -f phase9-gitops-platform/gitops-platform/applications/banking/shop-bridge.yaml -n argocd
argocd app sync banking-shop-bridge
```

4. Lab: `SHOP_BRIDGE_AUTO_CONFIRM=true` (trong `gitops/values-kafka.yaml`) → đặt hàng shop → ~3s đơn paid.  
   CK tay: set `false`, gọi:

```bash
oc -n npd-banking exec deploy/shop-bridge -- \
  curl -sS -X POST http://127.0.0.1:8010/api/shop/confirm-payment \
  -H 'Content-Type: application/json' \
  -d '{"transfer_ref":"NOLI-XXXX","amount_vnd":1290000}'
```

```bash
oc -n npd-banking logs deploy/shop-bridge --tail=50
# Kafka consumer started topic=orders.events
# shop order seen … / kafka published … payment.completed
```

---

## Bước 4c — Ecosystem Phase 1–3 (CK thật)

1. Tắt auto-confirm: `gitops/values-ecosystem.yaml` (`SHOP_BRIDGE_AUTO_CONFIRM=false`).
2. Rebuild **transfer-service** + **frontend** + **shop-bridge** (note + matcher + httpx).
3. Seed chủ shop:

```bash
python scripts/seed_huongly.py --base-url https://npd-banking.co --insecure
# → scripts/demo-huongly.json (account_number)
```

4. Điền STK vào:
   - `gitops/values-ecosystem.yaml` → `SHOP_MERCHANT_ACCOUNT_NUMBER`
   - `npd-shop/gitops/values-merchant.yaml` → `BANK_ACCOUNT_NUMBER`
5. Sync Argo `banking-transfer-service`, `banking-shop-bridge`, `npd-shop`.
6. Test: đặt đơn shop → login banking → CK đúng STK + nội dung `NOLI-…` → đơn Thành công.

---

## Bước 4d — Ecosystem cron (server riêng)

4 kịch bản + cron: `scripts/ecosystem/` (README trong thư mục).

```bash
cd banking-demo/scripts/ecosystem
sudo bash install.sh
# chỉnh /opt/npd-ecosystem/.env
sudo /opt/npd-ecosystem/bin/run-job.sh seed   # Ly 50tr, users 10tr, pass 123456, SĐT 09*
# điền LY_ACCOUNT_NUMBER + GitOps merchant STK (nếu chưa)
```

| Cron | Job |
|------|-----|
| `0 3 * * 0` | seed users |
| `*/10 * * * *` | peer CK 50k–500k |
| `0 */3 * * *` | mua shop + note `NOLI-*` |
| `0 12,18 * * *` | Ly nhập hàng @ 70% catalog |

Rebuild thêm **auth-service** + **account-service** (`initial_balance`, `admin/credit`).

---

## Bước 5 — Monitor (lab)

### A. OpenSearch logs (bank + shop + kafka)
Xem `phase9-gitops-platform/logging/DEPLOY.md`  
UI: https://logs-platform.apps.ocp01.npd.co — index pattern `npd-*`

### B. Kafka UI (chi tiết topic/message)
https://kafka-ui-platform.apps.ocp01.npd.co

### C. Coroot
1. Mở Coroot UI (Route coroot lab)
2. Filter namespace **`kafka`**
3. Kỳ vọng: pod brokers, CPU/mem, kết nối TCP từ `npd-shop` / `npd-banking` khi có traffic

### D. Instana
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
