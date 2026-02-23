# ArgoCD Applications – Banking Demo (Phase 5 / Phase 8)

Mỗi service một Application riêng. **Postgres, Redis, Kong** dùng Phase 5 (ns riêng) — không deploy qua chart banking-demo.

**Phase 8** (RabbitMQ): thêm `rabbitmq.yaml`, `api-producer.yaml`; Kong và services dùng `values-phase8.yaml`. Xem `../PHASE8-ARGOCD.md`.

## Cấu trúc Applications

| Application | Mô tả |
|-------------|-------|
| `namespace.yaml` | Namespace `banking` + Secret (DATABASE_URL, REDIS_URL Phase 5) |
| `rabbitmq.yaml` | RabbitMQ standalone (ns `rabbit`, Phase 8) |
| `kong.yaml` | Kong API Gateway (+ values-phase8 cho Phase 8) |
| `api-producer.yaml` | API Producer (Phase 8) |
| `auth-service.yaml` | Auth Service (+ values-phase8 cho Phase 8) |
| `account-service.yaml` | Account Service |
| `transfer-service.yaml` | Transfer Service |
| `notification-service.yaml` | Notification Service |
| `frontend.yaml` | Frontend React |
| `ingress.yaml` | Ingress (backend /api, /ws → Kong ns kong) |

## Deploy

```bash
kubectl apply -f applications/ -n argocd
```

## Thứ tự sync (sync waves)

1. **Wave -1**: namespace (tạo ns + secret)
2. **Wave 0**: rabbitmq (Phase 8, ns `rabbit`)
3. **Wave 1**: kong, api-producer (Phase 8)
4. **Wave 2**: auth, account, transfer, notification
5. **Wave 3**: frontend
6. **Wave 4**: ingress

## Điều kiện Phase 5

- Postgres HA, Redis HA, Kong HA đã deploy trong ns `postgres`, `redis`, `kong`
- Secret dùng: `postgres-postgresql-primary.postgres`, `redis.redis`, Kong proxy `kong-kong-proxy.kong`
- **Redis có auth**: Cần patch `banking-db-secret` với REDIS_URL có password — xem `MIGRATE-TO-PER-SERVICE.md` Bước 3

## Sync policy

| Application | selfHeal |
|-------------|----------|
| namespace | false |
| auth, account, transfer, notification, frontend, ingress | true |
