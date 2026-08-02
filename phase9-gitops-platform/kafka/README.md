# Shared platform Kafka (Strimzi) — Helm + ArgoCD

**Hướng dẫn triển khai từng bước:** [DEPLOY.md](./DEPLOY.md)

Kafka **không thuộc từng app** (shop/banking). Nằm ở **infra platform** dùng chung, giống Postgres / Redis / RabbitMQ.

```text
infra-app-of-apps
  ├── infra-postgres   (Helm Bitnami)
  ├── infra-redis      (Helm Bitnami)
  ├── infra-rabbitmq
  ├── infra-strimzi    (Helm Strimzi Operator)
  ├── infra-kafka      (Helm chart npd-kafka · cluster + topics)
  └── infra-kafka-ui   (Helm Kafbat UI · monitor)
         ↓
    ns kafka · bootstrap + UI dùng chung
         ├── banking
         └── npd-shop
```

| Argo Application | Chart | Namespace |
|------------------|-------|-----------|
| `infra-strimzi` | `https://strimzi.io/charts/` → `strimzi-kafka-operator` | `kafka` |
| `infra-kafka` | repo `phase9-gitops-platform/kafka/charts/npd-kafka` | `kafka` |
| `infra-kafka-ui` | `https://kafbat.github.io/helm-charts` → `kafka-ui` | `kafka` |

**UI:** https://kafka-ui-platform.apps.ocp01.npd.co  
Route: `environments/dev-ocp/ocp-values/routes/kafka-ui-route.yaml` (sync qua platform-routes).

Manifest apps:  
`gitops-platform/applications/infra/strimzi-operator.yaml`  
`gitops-platform/applications/infra/kafka.yaml`  
`gitops-platform/applications/infra/kafka-ui.yaml`

---

## Bootstrap (sau Ready)

| Mode | Address |
|------|---------|
| Lab (plain) | `npd-kafka-kafka-bootstrap.kafka.svc.cluster.local:9092` |
| Prod (TLS+SCRAM) | `…:9093` + Secret user `npd-shop` / `npd-banking` |

Shop: `npd-shop/gitops/values-kafka.yaml` → Argo Helm valueFiles.  
Banking: `gitops/values-kafka.yaml` + app **`banking-shop-bridge`** (user `npd-banking`).

Secrets sync (bastion):

```bash
# shop
bash ../npd-shop/deploy/scripts/sync-kafka-client-secrets.sh
# banking
bash phase9-gitops-platform/environments/dev-ocp/scripts/sync-kafka-client-secrets.sh
```

---

## Deploy

`infra-app-of-apps` đã recurse `applications/infra/` → sync/refresh app-of-apps (nhánh **dev-ocp**).

```bash
# AppProject (thêm strimzi helm repo + ns kafka — đã cập nhật project.yaml)
oc apply -f phase9-gitops-platform/gitops-platform/project.yaml -n argocd

# Nếu infra-app-of-apps trỏ nhánh khác, đảm bảo targetRevision = dev-ocp
oc -n argocd get application infra-strimzi infra-kafka infra-kafka-ui
oc -n kafka get kafka,kafkanodepool,kafkatopic,pod
oc -n kafka get route kafka-ui-platform
```

Thứ tự: **infra-strimzi** (wave 0) Ready → **infra-kafka** (wave 2).

---

## Values lab (NPD — chỉ nfs-csi)

| Mục | Giá trị |
|-----|---------|
| StorageClass | **`nfs-csi`** (không cần `kafka-block`) |
| PVC / broker | **20Gi** |
| RAM pod | **limit 4Gi**, heap JVM **2G** |
| Retention | **7 ngày** (`retention.ms` / `log.retention.hours=168`) |
| Cleanup | `cleanup.policy=delete` + check mỗi **5 phút** |
| Cap dung lượng | topic ~**2Gi**, broker default ~**1Gi/partition** (tránh đầy PVC trước 7 ngày) |
| Segment | **256Mi** (roll/xóa nhanh trên ổ nhỏ) |

`values-prod.yaml` = tắt plain + SCRAM/ACL, **vẫn nfs-csi 20Gi** (lab gần thật). Không đòi block storage.

---

## Checklist prod (map nhanh)

| Nguyên tắc | Nơi cấu hình |
|------------|--------------|
| 3 brokers + anti-affinity | `values` → `nodePool.replicas` + template affinity |
| RF=3, min.ISR=2 | `kafka.config` + topics |
| 5 partitions | `topics[].partitions` |
| lz4, retention **7 ngày** + cap bytes (PVC 20Gi) | `kafka.config` / `topicDefaults` |
| TLS+SCRAM+ACL (lab gần prod) | `values-prod.yaml` (vẫn nfs-csi) |
| Producer/consumer app | `npd-shop` `kafka_bus.py` / `payment-worker` |

Chi tiết checklist dài: giữ cùng nguyên tắc trong conversation / `values-prod.yaml`.

---

## Lưu ý

- **Không** gắn Kafka chart vào repo `npd-shop` — shop chỉ **consume** bootstrap platform.
- RabbitMQ vẫn nội bộ banking; Kafka = bus **cross-project**.
- Lab: **nfs-csi 20Gi**, RAM **4Gi**, message **xóa sau 7 ngày** (+ cap bytes để không đầy PVC).
- `values-prod.yaml` = bảo mật TLS/SCRAM trên cùng nfs — không cần StorageClass block.
