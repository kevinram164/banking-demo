# Phase 4 — Runbook: External Postgres / External Redis (DevOps checklist)

Tài liệu này dành cho tình huống **Postgres & Redis nằm ngoài cluster** (VM/Managed DB/Cloud service), app vẫn chạy trong K8s/Helm.

---

## 1) Network checklist (hay fail nhất)

### Postgres

- Port: **5432/TCP**
- Từ **node/pod CIDR** trong cluster có route tới DB network
- Firewall/Security Group allow inbound từ cluster (hoặc NAT/egress IP)
- Nếu DB có whitelist IP: whitelist **egress IP** của cluster

### Redis

- Port: **6379/TCP** (hoặc TLS port riêng)
- Tương tự Postgres: routing + firewall + whitelist

### Test nhanh từ cluster

Khuyến nghị tạo 1 pod debug tạm (toolbox):

```bash
kubectl -n banking run net-debug --rm -it --image=alpine:3.20 -- sh
```

Trong pod:

```sh
apk add --no-cache bind-tools busybox-extras
nslookup db.example.local
nc -vz db.example.local 5432
nc -vz redis.example.local 6379
```

---

## 2) TLS / SSL (Postgres managed thường bắt buộc)

Nếu DB yêu cầu SSL, bạn cần set:

- `sslmode=require` (hoặc `verify-ca`, `verify-full`)
- mount CA cert nếu dùng verify

Ví dụ `DATABASE_URL`:

```
postgresql://user:pass@db.example.local:5432/banking?sslmode=require
```

Nếu `verify-full`, hostname phải match cert CN/SAN.

---

## 3) Helm values cần set (Phase 2 chart)

### A) External Postgres

Trong `charts/common/values.yaml` đã có:

- `externalPostgres.enabled`
- `externalPostgres.host/port/db/user`
- password dùng từ Secret key `POSTGRES_PASSWORD`

**Gợi ý thao tác chuẩn:**

1) Tạo/Update Secret (banking namespace) chứa password thật:

```bash
kubectl -n banking create secret generic banking-db-secret \
  --from-literal=POSTGRES_PASSWORD='YOUR_DB_PASSWORD' \
  --dry-run=client -o yaml | kubectl apply -f -
```

2) Set `externalPostgres` khi helm upgrade (example):

```bash
helm upgrade --install banking-demo phase2-helm-chart/banking-demo \
  -n banking \
  -f phase2-helm-chart/banking-demo/charts/common/values.yaml \
  -f phase2-helm-chart/banking-demo/charts/kong/values.yaml \
  -f phase2-helm-chart/banking-demo/charts/postgres/values.yaml \
  --set externalPostgres.enabled=true \
  --set externalPostgres.host=db.example.local \
  --set externalPostgres.port=5432 \
  --set externalPostgres.db=banking \
  --set externalPostgres.user=banking \
  --set dbMigration.enabled=true
```

**Lưu ý**: nếu DB external thì bạn thường sẽ **tắt postgres chart** (không cần StatefulSet trong cluster):

```bash
--set postgres.enabled=false
```

### B) External Redis

Bạn chỉ cần set `REDIS_URL` trong Secret (hoặc values của services nếu chart đang đọc từ secretRef).

Ví dụ `REDIS_URL`:

```
redis://redis.example.local:6379/0
```

Nếu Redis có password:

```
redis://:PASSWORD@redis.example.local:6379/0
```

---

## 4) Migration (Helm hook) chạy được không khi DB external?

Chạy được nếu **pod Job** kết nối được đến DB external.

Hook Job trong chart (`templates/db-migration-job.yaml`) sẽ:

1) chạy `psql -c "select 1"` để test connection
2) chạy SQL migration (add columns, backfill, add indexes)
3) nếu fail → Helm upgrade fail (không rollout app)

---

## 5) Quy trình rollout chuẩn (không mắc lỗi)

### Recommended (Expand/Contract)

1) **Backup** DB trước
2) `helm upgrade` với `dbMigration.enabled=true` (hook chạy trước)
3) rollout app v2 (image tag)
4) verify: `/health`, login/transfer smoke test
5) (tuỳ chọn) tắt hook sau khi xong: `--set dbMigration.enabled=false`

---

## 6) Verify checklist sau deploy

### DB schema

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_name='users'
  AND column_name IN ('phone','account_number');
```

### Unique index

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename='users'
  AND indexname IN ('users_account_number_uq','users_phone_uq');
```

### Duplicate check (must be 0 rows)

```sql
SELECT account_number, count(*)
FROM users
WHERE account_number IS NOT NULL
GROUP BY account_number
HAVING count(*) > 1;
```

---

## 7) Rollback strategy

- Nếu hook migration chỉ **add columns + indexes**: rollback app image tag thường OK.
- Tránh làm migration phá huỷ (drop column) trong cùng release.
- Nếu migration fail: fix data/permissions/network rồi chạy `helm upgrade` lại.

