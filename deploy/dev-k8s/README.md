# Banking — dev-k8s

GitOps cho ứng dụng banking trên cụm kubeadm NPD. Platform và infra (Vault, Harbor, Jenkins, Postgres, Redis, RabbitMQ, Kong, Kafka, OTEL) do repo [cloud-native-platform](https://github.com/kevinram164/cloud-native-platform) quản lý, xem `phase9-gitops-platform/K8S-DEPLOY-GUIDE.md`.

## Cấu trúc

| Đường dẫn | Nội dung |
|-----------|----------|
| `argocd/appproject.yaml` | AppProject `banking` (chỉ repo này, ns `npd-banking`) |
| `argocd/app-of-apps.yaml` | Root `banking-root-dev-k8s` |
| `argocd/applications/` | namespace, 6 service, frontend, ingress (`npd-banking.co`, class `haproxy`) |
| `values/values-images.yaml` | Repository + tag image Harbor — Jenkins bump `tag` |
| `values/values-observability.yaml` | OTEL → collector ns `observability` |
| `values/values-kafka.yaml`, `values-ecosystem.yaml` | Shop-bridge ↔ Strimzi Kafka |
| `values/values-vault.yaml` | Bật Vault Agent Injector cho chart |

## Secret qua Vault Agent Injector

Khi `global.vault.enabled=true`, chart thêm annotation `vault.hashicorp.com/*` vào pod của auth, account, transfer, notification và api-producer. Init container `vault-agent-init` login role `banking-app` bằng ServiceAccount của pod, render `/vault/secrets/env`:

```sh
export DATABASE_URL='...'   # secret/banking/db
export REDIS_URL='...'      # secret/banking/db
export RABBITMQ_URL='...'   # secret/banking/rabbitmq
```

Container chạy `. /vault/secrets/env && exec uvicorn ...`, không còn `secretKeyRef` hay Secret `banking-db-secret` / `rabbitmq-connection-secret`. Đổi secret trong Vault thì restart deployment.

Shop-bridge vẫn đọc mật khẩu KafkaUser từ Secret `npd-banking-kafka-user` (Strimzi sinh, copy sang `npd-banking`).

## Triển khai

Điều kiện:

1. Infra trong `cloud-native-platform` đã Healthy.
2. Vault đã seed `secret/banking/db`, `secret/banking/rabbitmq` và chạy `vault-setup-k8s-auth.sh` (role `banking-app`).
3. Secret `harbor-pull-creds` trong `npd-banking` (`create-harbor-pull-secret.sh`).
4. Image đã có trên `npd-harbor.co/banking-demo` (Jenkins pipeline nhánh `dev-k8s`).

```bash
kubectl apply -f deploy/dev-k8s/argocd/appproject.yaml
kubectl apply -f deploy/dev-k8s/argocd/app-of-apps.yaml
```
