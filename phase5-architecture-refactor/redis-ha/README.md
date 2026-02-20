# Triển khai Redis HA và migrate data (Phase 5)

Deploy Bitnami Redis HA (master + replica), migrate session/presence từ Redis cũ (Phase 2) sang Redis mới.

---

## Bước 1: Deploy Redis HA

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

kubectl create namespace redis

helm upgrade -i redis bitnami/redis -n redis -f redis-ha/values-redis-ha.yaml
kubectl -n redis get pods -w
```

---

## Bước 2: Migrate data từ Redis cũ

Chạy khi Redis HA đã Ready và Redis cũ (ns banking) vẫn chạy:

```bash
kubectl apply -f redis-ha/migrate-redis-job.yaml -n redis
kubectl -n redis logs -f job/redis-migrate-from-banking
```

Sửa `OLD_HOST` trong Job nếu Phase 2 dùng tên khác (ví dụ `redis` khi cùng ns).

---

## Bước 3: Cập nhật app

Secret `banking-db-secret` cần `REDIS_URL`:

```
redis://redis.redis.svc.cluster.local:6379/0
```

Xem `APP-CUTOVER.md` cho hướng dẫn cutover đầy đủ.
