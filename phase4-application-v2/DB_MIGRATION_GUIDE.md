# Phase 4 (v2) — Hướng dẫn migrate DB (không mắc lỗi khi rollout)

## ⚠️ DB Migration phải chạy TRƯỚC khi deploy v2

Thứ tự bắt buộc: **1. ALTER bảng / migration DB** → 2. Deploy v2. Nếu deploy trước migration, app v2 sẽ crash (thiếu cột).

---

v2 thêm 2 cột vào bảng `users`:

- `phone` (unique)
- `account_number` (unique)

Đây là thay đổi **schema** nên nếu rollout kiểu “đổi code rồi deploy” rất dễ:

- Pod mới chạy lên nhưng DB chưa có cột → crash
- Hoặc add `NOT NULL + UNIQUE` sai thứ tự → fail khi data cũ chưa backfill
- Rollout dở dang (một nửa pod v1, một nửa pod v2) → conflict logic/query

Tài liệu này mô tả cách làm **an toàn**.

---

## Nguyên tắc: Expand / Contract

Với system đang chạy, luôn làm theo 2 bước:

1. **Expand**: thêm cột/index/constraint theo cách **backward-compatible** (code v1 vẫn chạy được).
2. Deploy code mới (v2).
3. **Contract**: dọn dẹp/siết chặt schema sau khi chắc chắn tất cả traffic đã ở v2.

---

## Kịch bản migrate an toàn cho `phone` + `account_number`

### Bước 0 — Chuẩn bị

- Chốt release: `v1.0.x` đang chạy ổn.
- Backup DB:

```bash
pg_dump -h <host> -U <user> -d <db> > backup_before_v2.sql
```

---

### Bước 1 (Expand) — Add columns (NULLable, chưa unique)

Chạy SQL migration (khuyến nghị dùng Alembic/Flyway/Liquibase; demo có thể chạy `psql`).

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS account_number VARCHAR(20);
```

Lưu ý: **chưa** set NOT NULL/UNIQUE ở bước này.

---

### Bước 2 — Backfill dữ liệu cho user cũ

Bạn cần backfill cho các bản ghi đã tồn tại để:

- `account_number` có giá trị duy nhất
- `phone` có giá trị duy nhất (tuỳ yêu cầu; nếu bắt buộc login bằng phone thì cần backfill)

Ví dụ backfill account number bằng hàm random (demo). Với production, bạn thường sẽ dùng:

- sequence + format (deterministic)
- hoặc table riêng giữ counter

Ví dụ (Postgres): tạo function sinh 12 số và loop tránh trùng.

```sql
DO $$
DECLARE
  r RECORD;
  candidate TEXT;
BEGIN
  FOR r IN SELECT id FROM users WHERE account_number IS NULL LOOP
    LOOP
      candidate := lpad((floor(random()*1e12))::bigint::text, 12, '0');
      EXIT WHEN NOT EXISTS (SELECT 1 FROM users WHERE account_number = candidate);
    END LOOP;
    UPDATE users SET account_number = candidate WHERE id = r.id;
  END LOOP;
END $$;
```

**Phone**: nếu bạn không có phone thật cho user cũ, có 2 lựa chọn chuẩn:

- **Option A (khuyến nghị)**: cho phép `phone` NULL tạm thời, chỉ user mới bắt buộc phone.
- **Option B**: backfill phone “giả” theo rule nội bộ (ví dụ `999000<ID>`), nhưng phải đảm bảo không trùng và không leak ra ngoài.

---

### Bước 3 — Add unique index (concurrently) sau khi sạch dữ liệu

Thêm unique index khi đã đảm bảo:

- không có duplicate
- không còn NULL nếu bạn muốn `NOT NULL`

Khuyến nghị tạo index **CONCURRENTLY** để hạn chế lock (production).

```sql
-- account_number
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS users_account_number_uq
ON users(account_number)
WHERE account_number IS NOT NULL;

-- phone (nếu bắt buộc unique)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS users_phone_uq
ON users(phone)
WHERE phone IS NOT NULL;
```

---

### Bước 4 — Deploy v2 (rolling)

Khi DB đã có cột + index, bạn mới deploy v2.

Điểm quan trọng khi rollout:

- v2 code phải **chịu được** record cũ (ví dụ phone NULL nếu bạn chọn Option A).
- không đổi logic “hard break” trong giai đoạn mixed pods.

---

### Bước 5 (Contract) — siết NOT NULL (chỉ khi chắc chắn)

Chỉ set `NOT NULL` sau khi:

- backfill hoàn tất
- đảm bảo tất cả service version đều đã nâng cấp
- verify không có NULL/duplicate

```sql
ALTER TABLE users ALTER COLUMN account_number SET NOT NULL;
-- phone: chỉ set nếu bạn thực sự bắt buộc tất cả user phải có phone
-- ALTER TABLE users ALTER COLUMN phone SET NOT NULL;
```

---

## DevOps best practices (khi dùng Helm/K8s)

### 1) Migrate bằng Job (không chạy trong app container)

Pattern chuẩn:

- Deploy một `Job` chạy migration (Alembic/Flyway)
- Job chạy **trước** khi rollout Deployment
- Nếu migration fail → dừng rollout

Với Helm, thường làm theo 1 trong 2 cách:

- **Helm hook**: `helm.sh/hook: pre-install,pre-upgrade`
- Hoặc pipeline CI chạy `kubectl apply -f migrate-job.yaml` rồi mới `helm upgrade`

### 2) Rollback strategy

- Nếu chỉ là **Expand** (add column/index) thì rollback code thường OK.
- Tránh migration “destructive” (drop column) trong cùng release với code change.

### 3) Kiểm tra trước khi deploy

Các câu SQL nên có “guard”:

- `IF NOT EXISTS`
- check duplicate trước khi tạo unique index

```sql
SELECT account_number, count(*)
FROM users
WHERE account_number IS NOT NULL
GROUP BY account_number
HAVING count(*) > 1;
```

---

## TL;DR quy trình chuẩn (đi làm)

1. Backup
2. Expand: add columns nullable
3. Backfill
4. Add unique indexes
5. Deploy v2
6. Contract: set NOT NULL (nếu cần)

