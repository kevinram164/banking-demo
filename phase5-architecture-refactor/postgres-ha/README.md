# Triển khai Postgres HA và migrate data từ DB cũ (Phase 5)

Hướng dẫn: pull chart Bitnami PostgreSQL (HA/replication), thêm file values, deploy vào namespace riêng, rồi migrate data từ Postgres cũ (Phase 2) sang Postgres mới.

---

## Bước 1: Pull chart và tạo file values

```bash
# Thêm repo Bitnami
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Pull chart về (tùy chọn – để xem structure)
helm pull bitnami/postgresql --untar -d postgres-ha/
# Hoặc cài trực tiếp không cần pull (dùng -f values)
```

Tạo file `values-postgres-ha.yaml` trong thư mục `postgres-ha/` (xem nội dung bên dưới).

---

## Bước 2: Deploy Postgres HA (mới, trống)

```bash
# Tạo namespace postgres (nếu chưa có)
kubectl create namespace postgres

# Cài Postgres HA (primary + 1 read replica)
helm upgrade -i postgres-ha bitnami/postgresql \
  -n postgres \
  -f postgres-ha/values-postgres-ha.yaml

# Chờ primary Ready
kubectl -n postgres get pods -l app.kubernetes.io/name=postgresql -w
# Ctrl+C khi postgres-postgresql-primary-0 Running, Ready 1/1
```

**Lưu ý**: Postgres mới đang trống (chưa có schema/data). DB `banking` và user `banking` được tạo qua values.

---

## Bước 3: Migrate data từ DB cũ sang DB mới

### 3.1. Xác định địa chỉ DB cũ và DB mới

- **DB cũ (Phase 2)**: Thường trong ns `banking`, Service `postgres`, port 5432. Pod: `postgres-0` (StatefulSet).
- **DB mới (Phase 5)**: ns `postgres`, Service `postgres-postgresql-primary.postgres.svc.cluster.local` (Bitnami), port 5432.

### 3.2. Cách 1: Dump và restore thủ công (kubectl exec + port-forward)

```bash
# Port-forward DB cũ ra local (terminal 1)
kubectl -n banking port-forward svc/postgres 5432:5432

# Dump từ DB cũ (terminal 2, dùng psql/pg_dump local hoặc pod)
kubectl -n banking exec -it postgres-0 -- env PGPASSWORD=bankingpass \
  pg_dump -U banking -d banking -F c -f /tmp/banking.dump

# Copy dump ra local (nếu dùng pg_restore local)
kubectl -n banking cp postgres-0:/tmp/banking.dump ./banking.dump

# Port-forward DB mới
kubectl -n postgres port-forward svc/postgres-postgresql-primary 5433:5432

# Restore vào DB mới (local)
PGPASSWORD=bankingpass pg_restore -h localhost -p 5433 -U banking -d banking --clean --if-exists ./banking.dump
```

### 3.3. Cách 2: Job migrate trong cluster (khuyến nghị)

Job chạy trong cluster, kết nối trực tiếp tới cả hai DB (không cần port-forward).

```bash
# Áp dụng Job migrate
kubectl apply -f postgres-ha/migrate-db-job.yaml -n postgres
kubectl -n postgres get jobs
kubectl -n postgres logs -f job/postgres-migrate-from-banking
```

Job sẽ:
1. `pg_dump` từ DB cũ (`postgres.banking.svc.cluster.local`)
2. `pg_restore` vào DB mới (`postgres-postgresql-primary.postgres.svc.cluster.local`)

**Lưu ý**: Cần sửa `migrate-db-job.yaml` nếu tên Service/namespace DB cũ khác (ví dụ release name khác).

### 3.4. Kiểm tra DB sau khi migrate

Sau khi Job migrate hoàn thành, kiểm tra dữ liệu đã được restore đúng:

```bash
# Lấy password
export POSTGRES_PASSWORD=$(kubectl get secret --namespace postgres postgres-postgresql -o jsonpath="{.data.password}" | base64 -d)

# Kiểm tra danh sách bảng trong DB banking
kubectl run postgres-check --rm -it --restart=Never -n postgres \
  --image=bitnami/postgresql:latest \
  --env="PGPASSWORD=$POSTGRES_PASSWORD" \
  -- psql -h postgres-postgresql-primary -U banking -d banking -c "\dt"

# Kiểm tra số lượng bản ghi (ví dụ: bảng accounts, transfers)
kubectl run postgres-check --rm -it --restart=Never -n postgres \
  --image=bitnami/postgresql:latest \
  --env="PGPASSWORD=$POSTGRES_PASSWORD" \
  -- psql -h postgres-postgresql-primary -U banking -d banking -c "SELECT 'accounts' AS tbl, count(*) FROM accounts UNION ALL SELECT 'transfers', count(*) FROM transfers;"

# (Tùy chọn) Kiểm tra replica đang stream từ primary
kubectl run postgres-check --rm -it --restart=Never -n postgres \
  --image=bitnami/postgresql:latest \
  --env="PGPASSWORD=$POSTGRES_PASSWORD" \
  -- psql -h postgres-postgresql-primary -U postgres -d postgres -c "SELECT client_addr, state, sync_state FROM pg_stat_replication;"
```

- `\dt` liệt kê các bảng – đảm bảo schema đã có.
- So sánh `count(*)` với DB cũ để xác nhận số bản ghi.
- `pg_stat_replication` cho thấy replica có `state = streaming` là đang sync.

---

## Bước 4: Cập nhật Banking app trỏ sang DB mới

1. Tạo hoặc cập nhật Secret `banking-db-secret` trong ns `banking`:

```yaml
# DATABASE_URL trỏ tới Postgres mới (primary)
DATABASE_URL=postgresql://banking:bankingpass@postgres-postgresql-primary.postgres.svc.cluster.local:5432/banking
```

2. Restart các deployment app (auth-service, account-service, transfer-service, notification-service) để đọc Secret mới:

```bash
kubectl -n banking rollout restart deployment auth-service account-service transfer-service notification-service
```

3. (Phase 2 thu gọn) Tắt Postgres cũ trong chart banking-demo: set `postgres.enabled: false` trong values.

---

## Bước 5: Kiểm tra và cutover

1. Đăng nhập, chuyển tiền, tạo thông báo – xác nhận app hoạt động với DB mới.
2. Khi ổn định: xóa hoặc scale down Postgres cũ trong ns `banking` (nếu vẫn còn).
3. (Tùy chọn) Chạy migration Phase 4 v2 (phone, account_number) nếu chưa chạy – Job migration DB của Phase 4 có thể trỏ tới DB mới qua `externalPostgres` hoặc env.

---

## Tóm tắt thứ tự

1. `helm repo add bitnami ...` + `helm repo update`
2. Tạo `values-postgres-ha.yaml`
3. `helm upgrade -i postgres-ha bitnami/postgresql -n postgres -f values-postgres-ha.yaml`
4. Migrate: Job `migrate-db-job.yaml` hoặc pg_dump/pg_restore thủ công
5. **Kiểm tra DB**: `\dt`, `count(*)` các bảng, `pg_stat_replication`
6. Cập nhật Secret + restart app, tắt Postgres cũ
