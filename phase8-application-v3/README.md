# Phase 8 — Kong → API Producer → RabbitMQ → Consumers

Kiến trúc: Kong nhận HTTP → API Producer publish → RabbitMQ → Consumers (auth, account, transfer, notification) → Response qua Redis.

## Luồng

1. **Kong** route `/api/*` → api-producer:8080, `/ws` → notification-service:8004
2. **API Producer** nhận HTTP, map path → queue, publish → RabbitMQ, chờ response qua Redis
3. **Consumers** (auth, account, transfer, notification) consume từ queue, xử lý, ghi response vào Redis
4. **Producer** đọc response từ Redis, trả HTTP cho client

```mermaid
flowchart TB
    subgraph Client
        Browser[Browser / Client]
    end

    subgraph Kong["Kong API Gateway"]
        KongProxy[Proxy :8000]
    end

    subgraph Phase8["Phase 8 - Banking Demo"]
        subgraph Producer["API Producer :8080"]
            ProducerHTTP[HTTP Handler]
            ProducerPublish[Publish to RabbitMQ]
            ProducerWait[Wait Redis Response]
        end

        subgraph RabbitMQ["RabbitMQ"]
            Q1[auth.requests]
            Q2[account.requests]
            Q3[transfer.requests]
            Q4[notification.requests]
        end

        subgraph Consumers["Consumers"]
            Auth[auth-service]
            Account[account-service]
            Transfer[transfer-service]
            Notif[notification-service]
        end

        subgraph Redis["Redis"]
            ResponseStore["response:correlation_id"]
        end

        subgraph Direct["Direct - bypass queue"]
            NotifWS[notification-service /ws]
        end
    end

    subgraph DB["PostgreSQL"]
        Database[(Database)]
    end

    Browser -->|"HTTP /api/*"| KongProxy
    KongProxy -->|"/api/*"| ProducerHTTP
    KongProxy -->|"/ws"| NotifWS

    ProducerHTTP --> ProducerPublish
    ProducerPublish --> Q1 & Q2 & Q3 & Q4
    Q1 --> Auth
    Q2 --> Account
    Q3 --> Transfer
    Q4 --> Notif

    Auth & Account & Transfer & Notif -->|"store_response"| ResponseStore
    ProducerWait -->|"poll GET"| ResponseStore
    ResponseStore --> ProducerWait

    ProducerWait -->|"HTTP Response"| ProducerHTTP
    ProducerHTTP --> KongProxy
    KongProxy --> Browser

    Auth & Account & Transfer & Notif --> Database
```
## Queues

- `auth.requests` — register, login
- `account.requests` — me, balance, lookup, admin/*
- `transfer.requests` — transfer
- `notification.requests` — GET /notifications

WebSocket `/ws` đi trực tiếp tới notification-service (không qua queue).

## Kong (ns kong) — QUAN TRỌNG khi dùng Ingress kong-proxy-ext

Nếu traffic đi qua **Kong trong ns `kong`** (ingress backend: kong-proxy-ext → kong-kong-proxy.kong), phải cấu hình Kong route `/api` → **api-producer** (không route trực tiếp tới auth/account/transfer).

**Cách apply (giống Phase 5) — Job import config vào Kong DB:**
```bash
kubectl apply -f phase8-application-v3/kong-ha/kong-import-job.yaml
# Đợi Job chạy xong, sau đó RESTART Kong để load config mới
kubectl rollout restart deployment -n kong -l app.kubernetes.io/name=kong
# (hoặc statefulset nếu Kong dùng StatefulSet)
```

Job tạo ConfigMap `kong-declarative-config-phase8` và chạy `kong config db_import` vào Kong PostgreSQL. **Bắt buộc restart Kong** để áp dụng config. Cần chỉnh env `KONG_PG_*` trong Job nếu Kong dùng DB khác.

**Nếu đang từ Phase 5:** Kong có thể còn routes cũ. Kong OSS **Route không có field `enabled`** — phải **xóa** routes:
```bash
curl -s -X DELETE http://kong-kong-admin:8001/routes/auth-route
curl -s -X DELETE http://kong-kong-admin:8001/routes/account-route
curl -s -X DELETE http://kong-kong-admin:8001/routes/transfer-route
curl -s -X DELETE http://kong-kong-admin:8001/routes/notification-route
```
Sau khi xóa, api-route nhận toàn bộ /api/*. notification-ws-route (/ws) vẫn giữ nguyên.

**Rollback:** Import lại kong-phase5.yml hoặc tạo lại 4 routes từ config Phase 5.

**Thêm route /ws nếu thiếu** (WebSocket notification):
```bash
# Lấy service id của notification-service
SVC_ID=$(curl -s http://kong-kong-admin:8001/services/notification-service | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

# Tạo route /ws (nếu SVC_ID rỗng thì tạo service trước)
curl -s -X POST http://kong-kong-admin:8001/services/notification-service/routes \
  -H "Content-Type: application/json" \
  -d '{"name":"notification-ws-route","paths":["/ws"],"strip_path":false,"protocols":["http","https"]}'
```

Nếu chưa có service `notification-service`, tạo trước:
```bash
curl -s -X POST http://kong-kong-admin:8001/services \
  -H "Content-Type: application/json" \
  -d '{"name":"notification-service","url":"http://notification-service.banking.svc.cluster.local:8004"}' && \
curl -s -X POST http://kong-kong-admin:8001/services/notification-service/routes \
  -H "Content-Type: application/json" \
  -d '{"name":"notification-ws-route","paths":["/ws"],"strip_path":false,"protocols":["http","https"]}'
```

**File config tham khảo:** `phase8-application-v3/kong-phase8.yml`

## Triển khai RabbitMQ

RabbitMQ triển khai **riêng** trên namespace `rabbit`. Credentials lưu trong **Secret riêng**, **không** ghi vào values file.

### 1. Namespace và Secret cho RabbitMQ (ns `rabbit`)

```bash
kubectl create namespace rabbit

# Secret — tạo thủ công, KHÔNG commit vào git
kubectl create secret generic rabbitmq-secret \
  --from-literal=rabbitmq-username=banking \
  --from-literal=rabbitmq-password='<PASSWORD>' \
  -n rabbit
```

### 2. Cài đặt RabbitMQ

**Option A — Official image** (khuyến nghị khi Bitnami ImagePullBackOff):

```bash
kubectl apply -f phase8-application-v3/rabbitmq/k8s-rabbitmq-standalone.yaml
```

Dùng image `rabbitmq:3.12-management`, persistence với StorageClass `nfs-client` (8Gi). Resources: limits memory 1Gi, cpu 1000m.

**Option B — Bitnami Legacy** (image tại `bitnamilegacy/rabbitmq`, không còn cập nhật):

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

helm install rabbitmq bitnami/rabbitmq -n rabbit -f - <<EOF
global:
  security:
    allowInsecureImages: true  # Cần khi dùng bitnamilegacy

image:
  registry: docker.io
  repository: bitnamilegacy/rabbitmq
  tag: 3.10.12-debian-11-r4

auth:
  username: banking
  existingPasswordSecret: "rabbitmq-secret"
  existingSecretPasswordKey: "rabbitmq-password"

replicaCount: 3
clustering:
  enabled: true
  rebalance: true

persistence:
  enabled: true
  storageClass: "nfs-client"
  size: 8Gi

resources:
  limits:
    memory: 1Gi
    cpu: "1000m"
  requests:
    memory: 256Mi
    cpu: "100m"

metrics:
  enabled: true
EOF
```

**Option C — Bitnami mới (OCI):** Nếu `bitnami/rabbitmq` pull được:

```bash
helm install rabbitmq oci://registry-1.docker.io/bitnamicharts/rabbitmq -n rabbit -f - <<EOF
auth:
  username: banking
  existingPasswordSecret: "rabbitmq-secret"
  existingSecretPasswordKey: "rabbitmq-password"

replicaCount: 3
clustering:
  enabled: true
  rebalance: true

persistence:
  enabled: true
  storageClass: "nfs-client"
  size: 8Gi

resources:
  limits:
    memory: 1Gi
    cpu: "1000m"
  requests:
    memory: 256Mi
    cpu: "100m"

metrics:
  enabled: true
EOF
```

Nếu gặp `manifest unknown` / `ImagePullBackOff`, dùng Option A (official) hoặc Option B (legacy).

### 3. Secret connection cho banking-demo (ns `banking-demo`)

Producer và consumers đọc `RABBITMQ_URL` từ Secret `rabbitmq-connection-secret`. **Tạo thủ công**, không ghi vào values:

```bash
# Thay <PASSWORD> bằng password đã dùng ở bước 1
kubectl create secret generic rabbitmq-connection-secret \
  --from-literal=RABBITMQ_URL='amqp://banking:<PASSWORD>@rabbitmq.rabbit.svc.cluster.local:5672/' \
  -n banking
```

Values-phase8.yaml chỉ khai báo `rabbitmqSecretRef.name` và `key`, không chứa URL hay password.


## Build và deploy

### Build images

```bash
# Build từ repo root
docker build -f phase8-application-v3/producer/Dockerfile . -t registry.gitlab.com/kiettt164/banking-demo-payment/api-producer:latest
docker build -f phase8-application-v3/services/auth-service/Dockerfile . -t registry.gitlab.com/.../auth-service:v3
docker build -f phase8-application-v3/services/account-service/Dockerfile . -t registry.gitlab.com/.../account-service:v3
docker build -f phase8-application-v3/services/transfer-service/Dockerfile . -t registry.gitlab.com/.../transfer-service:v3
docker build -f phase8-application-v3/services/notification-service/Dockerfile . -t registry.gitlab.com/.../notification-service:v3
```

### Deploy banking-demo

**Lưu ý:** RabbitMQ deploy riêng ns `rabbit`. Trước khi deploy banking-demo, tạo Secret `rabbitmq-connection-secret` trong ns `banking-demo` (xem mục Triển khai RabbitMQ).

```bash
cd phase2-helm-chart/banking-demo
# values-phase8.yaml PHẢI đặt cuối
helm upgrade --install banking-demo . -n banking-demo \
  -f charts/common/values.yaml \
  -f charts/auth-service/values.yaml \
  -f charts/account-service/values.yaml \
  -f charts/transfer-service/values.yaml \
  -f charts/notification-service/values.yaml \
  -f charts/api-producer/values.yaml \
  -f charts/kong/values.yaml \
  -f charts/frontend/values.yaml \
  -f values-phase8.yaml
```

**Lưu ý:** Phase 8 cần override image tag cho auth/account/transfer/notification sang v3 khi deploy. Thêm vào values-phase8.yaml hoặc dùng `--set`:

```bash
--set auth-service.image.tag=v3 \
--set account-service.image.tag=v3 \
--set transfer-service.image.tag=v3 \
--set notification-service.image.tag=v3
```

### Rollback về Phase 2/4

```bash
helm upgrade banking-demo . -n banking-demo -f charts/common/values.yaml -f charts/auth-service/values.yaml ...
# (không dùng values-phase8.yaml)
```

## Monitoring (Grafana)

Phase 8 dùng **api-producer** làm entry point cho toàn bộ HTTP API; consumers không expose `/metrics` HTTP nữa. Dashboard "Banking Services" cần:

1. **Prometheus scrape** api-producer:8080 — đã thêm job `api-producer` trong `phase3-monitoring-keda/helm-monitoring/values-kube-prometheus-stack.yaml`
2. **Dashboard** — `banking-services.json` đã cập nhật để:
   - Thêm `api-producer` vào job selector
   - Stat panels (Auth/Account/Transfer/Notification RPS) dùng `or` để lấy cả Phase 4/5 (job trực tiếp) và Phase 8 (api-producer + endpoint regex)
   - Transfer panels dùng `endpoint=~"/transfer|/api/transfer.*"` cho cả hai phase

Sau khi upgrade helm-monitoring, đợi Prometheus scrape xong (1–2 phút) rồi refresh Grafana dashboard.

## Cấu trúc

- `common/` — db, models, redis, rabbitmq_utils, health_server
- `producer/` — FastAPI nhận HTTP, publish/wait
- `services/auth-service/` — consumer auth.requests
- `services/account-service/` — consumer account.requests
- `services/transfer-service/` — consumer transfer.requests
- `services/notification-service/` — consumer + WebSocket /ws
