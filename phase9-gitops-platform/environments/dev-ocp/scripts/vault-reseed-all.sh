#!/usr/bin/env bash
# Re-seed toàn bộ Vault KV sau khi Vault dev mode mất data (restart / mất điện).
# Dev mode = in-memory → mọi secret + kubernetes auth mất sau khi pod vault-0 restart.
#
# Chạy trên bastion (đã oc login), truyền password thật qua env:
#   export MOVIE_DB_PASSWORD=Tech1604
#   ./environments/dev-ocp/scripts/vault-reseed-all.sh
#
# Idempotent: chạy lại nhiều lần được (vault kv put ghi đè).
set -euo pipefail

VAULT_NS="${VAULT_NS:-vault}"
VAULT_POD="${VAULT_POD:-vault-0}"
VAULT_TOKEN="${VAULT_TOKEN:-root}"

# --- Secret values (đổi cho khớp môi trường) ---
DB_URL="${DATABASE_URL:-postgresql://banking:bankingpass@postgres-ha-postgresql-primary.postgres.svc.cluster.local:5432/banking}"
REDIS_URL="${REDIS_URL:-sentinel://:Mbfs%402025@redis-ha.redis.svc.cluster.local:26379/0/mymaster}"
RABBITMQ_URL="${RABBITMQ_URL:-amqp://banking:bankingpass@rabbitmq.rabbit.svc.cluster.local:5672/}"
RABBIT_USER="${RABBIT_USER:-banking}"
RABBIT_PASS="${RABBIT_PASS:-bankingpass}"

HARBOR_HOST="${HARBOR_HOST:-harbor-platform.apps.ocp01.npd.co}"
HARBOR_CI_USER="${HARBOR_CI_USER:-robot\$banking-demo+ci-push}"
HARBOR_CI_PASS="${HARBOR_CI_PASS:-mcQ6lbvYfEblZMd22W1m7efOjaQvlKTd}"
HARBOR_PULL_USER="${HARBOR_PULL_USER:-robot\$banking-demo+k8s-pull}"
HARBOR_PULL_PASS="${HARBOR_PULL_PASS:-DojqMAuUdZcBh2aI9wFSEHaocLY1MgFx}"

GITHUB_USER="${GITHUB_USER:-kevinram164}"
GITHUB_PAT="${GITHUB_PAT:-CHANGE_ME_GITHUB_PAT}"

JENKINS_ADMIN_USER="${JENKINS_ADMIN_USER:-admin}"
JENKINS_ADMIN_PASS="${JENKINS_ADMIN_PASS:-ChangeMe-Jenkins}"

# CineHome (movie-web) — chỉ seed nếu SEED_CINEHOME=1
SEED_CINEHOME="${SEED_CINEHOME:-1}"
MOVIE_DB_PASSWORD="${MOVIE_DB_PASSWORD:-Tech1604}"
CINEHOME_HARBOR_CI_USER="${CINEHOME_HARBOR_CI_USER:-robot\$movie-web+ci-push}"
CINEHOME_HARBOR_CI_PASS="${CINEHOME_HARBOR_CI_PASS:-ehUpDsBS2q5kjMtKPD0oeTwV3AIo6UOQ}"
CINEHOME_HARBOR_PULL_USER="${CINEHOME_HARBOR_PULL_USER:-robot\$movie-web+k8s-pull}"
CINEHOME_HARBOR_PULL_PASS="${CINEHOME_HARBOR_PULL_PASS:-hu8HxXewcaV57hlJ9FAEHNQ78J7H6xMB}"
MINIO_USER="${MINIO_USER:-minioadmin}"
MINIO_PASS="${MINIO_PASS:-Tech1604}"
MOVIE_DATABASE_URL="${MOVIE_DATABASE_URL:-postgresql+psycopg2://movie:${MOVIE_DB_PASSWORD}@postgres-ha-postgresql-primary.postgres.svc.cluster.local:5432/movie}"
MOVIE_REDIS_URL="${MOVIE_REDIS_URL:-redis://:Mbfs%402025@redis-ha.redis.svc.cluster.local:6379/0}"

echo "==> Đợi ${VAULT_POD} Running (ns ${VAULT_NS})"
oc rollout status -n "${VAULT_NS}" statefulset/vault --timeout=120s 2>/dev/null || \
  oc wait --for=condition=Ready pod/"${VAULT_POD}" -n "${VAULT_NS}" --timeout=120s

echo "==> Seed KV trong ${VAULT_POD}"
oc exec -i -n "${VAULT_NS}" "${VAULT_POD}" -- sh -s <<EOF
set -e
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN='${VAULT_TOKEN}'

# KV v2 engine (dev mode đã bật secret/ sẵn — bỏ qua lỗi nếu đã có)
vault secrets enable -path=secret kv-v2 2>/dev/null || true

# --- Banking ---
vault kv put secret/banking/db \
  DATABASE_URL='${DB_URL}' \
  REDIS_URL='${REDIS_URL}'

vault kv put secret/banking/rabbitmq \
  RABBITMQ_URL='${RABBITMQ_URL}'

vault kv put secret/rabbitmq/admin \
  username='${RABBIT_USER}' \
  password='${RABBIT_PASS}'

# --- Platform ---
vault kv put secret/platform/harbor \
  username='${HARBOR_CI_USER}' \
  password='${HARBOR_CI_PASS}'

vault kv put secret/platform/harbor-pull \
  registry='${HARBOR_HOST}' \
  username='${HARBOR_PULL_USER}' \
  password='${HARBOR_PULL_PASS}'

vault kv put secret/platform/github \
  username='${GITHUB_USER}' \
  pat='${GITHUB_PAT}'

vault kv put secret/platform/jenkins \
  admin_username='${JENKINS_ADMIN_USER}' \
  admin_password='${JENKINS_ADMIN_PASS}'
EOF

if [ "${SEED_CINEHOME}" = "1" ]; then
  echo "==> Seed CineHome KV"
  oc exec -i -n "${VAULT_NS}" "${VAULT_POD}" -- sh -s <<EOF
set -e
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN='${VAULT_TOKEN}'

vault kv put secret/cinehome/harbor \
  username='${CINEHOME_HARBOR_CI_USER}' \
  password='${CINEHOME_HARBOR_CI_PASS}'

vault kv put secret/cinehome/harbor-pull \
  registry='${HARBOR_HOST}' \
  username='${CINEHOME_HARBOR_PULL_USER}' \
  password='${CINEHOME_HARBOR_PULL_PASS}'

vault kv put secret/cinehome/movie-db \
  username='movie' \
  password='${MOVIE_DB_PASSWORD}' \
  database='movie'

vault kv put secret/cinehome/app \
  DATABASE_URL='${MOVIE_DATABASE_URL}' \
  REDIS_URL='${MOVIE_REDIS_URL}' \
  MINIO_ACCESS_KEY='${MINIO_USER}' \
  MINIO_SECRET_KEY='${MINIO_PASS}'

vault kv put secret/cinehome/minio \
  rootUser='${MINIO_USER}' \
  rootPassword='${MINIO_PASS}'
EOF
fi

echo "==> Bật lại Kubernetes auth + policy + role cho Jenkins (mất theo dev mode)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${SCRIPT_DIR}/vault-setup-jenkins-k8s-auth.sh" ]; then
  VAULT_TOKEN="${VAULT_TOKEN}" bash "${SCRIPT_DIR}/vault-setup-jenkins-k8s-auth.sh" || \
    echo "WARN: vault-setup-jenkins-k8s-auth.sh lỗi — chạy tay nếu cần"
fi

echo "==> Force-sync ESO (đọc lại Vault)"
for es in $(oc get externalsecret -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{"\n"}{end}' 2>/dev/null); do
  ns="${es%%/*}"; name="${es##*/}"
  oc annotate externalsecret "${name}" -n "${ns}" force-sync="$(date +%s)" --overwrite >/dev/null 2>&1 || true
done

echo ""
echo "OK — Vault đã re-seed. Kiểm tra:"
echo "  oc exec -n ${VAULT_NS} ${VAULT_POD} -- sh -c 'export VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=${VAULT_TOKEN}; vault kv list secret/'"
echo "  oc get externalsecret -A"
