# ArgoCD Applications – Banking Demo (Phase 5)

Mỗi service một Application riêng. **Postgres, Redis, Kong** dùng Phase 5 (ns riêng) — không deploy qua chart banking-demo.

## Cấu trúc Applications

| Application | Mô tả |
|-------------|-------|
| `namespace.yaml` | Namespace `banking` + Secret (DATABASE_URL, REDIS_URL Phase 5) |
| `auth-service.yaml` | Auth Service |
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
2. **Wave 2**: auth, account, transfer, notification
3. **Wave 3**: frontend
4. **Wave 4**: ingress

## Điều kiện Phase 5

- Postgres HA, Redis HA, Kong HA đã deploy trong ns `postgres`, `redis`, `kong`
- Secret dùng: `postgres-postgresql-primary.postgres`, `redis.redis`, Kong proxy `kong-kong-proxy.kong`
- **Redis có auth**: Cần patch `banking-db-secret` với REDIS_URL có password — xem `MIGRATE-TO-PER-SERVICE.md` Bước 3

## Sync policy

| Application | selfHeal |
|-------------|----------|
| namespace | false |
| auth, account, transfer, notification, frontend, ingress | true |
