# K8s Chatbot

Chatbot quản lý và trace cụm Kubernetes qua ngôn ngữ tự nhiên.

📖 **[Tài liệu đầy đủ](docs/README.md)** — Kiến trúc, cài đặt, cấu hình, Ollama, RAG, API, troubleshooting.

## Tính năng

- **Kubernetes**: Check pods, deployments, rollout restart, logs
- **Loki**: Tìm logs lỗi (LogQL)
- **Prometheus**: Query metrics (PromQL)
- **LLM**: Parse câu lệnh tự nhiên (OpenAI / Ollama)
- **RAG**: Chroma vector DB — retrieve similar examples để cải thiện parse
- **analyze_logs**: Phân tích logs qua LLM — fetch logs → LLM tìm bất thường/lỗi

## Chạy local

### Backend

```bash
cd k8s-chatbot/backend
pip install -r requirements.txt

# Cần kubeconfig trỏ tới cluster
export K8S_IN_CLUSTER=false

# (Tùy chọn) LLM - nếu không có sẽ dùng rule-based
export OPENAI_API_KEY=sk-...
# Hoặc Ollama:
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_MODEL=llama3

uvicorn main:app --reload --port 8080
```

### Frontend

```bash
cd k8s-chatbot/frontend
npm install
npm run dev
```

Frontend chạy ở http://localhost:5173, proxy `/api` tới backend 8080.

## Build & Deploy

### Docker

```bash
# Build image (từ thư mục k8s-chatbot)
docker build -t k8s-chatbot:latest .
```

### Helm

```bash
# Cần có monitoring stack (Prometheus, Loki) trong ns monitoring
# Cần Secret gitlab-registry trong ns k8s-chatbot (copy từ banking nếu đã có):
#   kubectl get secret gitlab-registry -n banking -o yaml | sed 's/namespace: banking/namespace: k8s-chatbot/' | grep -v resourceVersion | grep -v uid | kubectl apply -f -
helm install k8s-chatbot ./helm -n k8s-chatbot --create-namespace

# Với custom values
helm upgrade --install k8s-chatbot ./helm -n k8s-chatbot -f helm/values.yaml
```

### CI (GitHub Actions)

- Workflow: `.github/workflows/k8s-chatbot-ci.yml`
- Trigger: push/PR khi `k8s-chatbot/**` thay đổi
- Registry: `registry.gitlab.com/kiettt164/banking-demo-payment/k8s-chatbot`
- Secrets: `GITLAB_USERNAME`, `GITLAB_TOKEN` (dùng chung với banking CI)

### RBAC

Chart tạo ServiceAccount `k8s-chatbot` với ClusterRole:
- `get`, `list`, `watch` pods, pods/log
- `get`, `list`, `watch`, `patch` deployments

## Ví dụ lệnh

| Lệnh | Hành động |
|------|-----------|
| Check status pods của ns banking | `kubectl get pods -n banking` |
| Rollout restart deployment của ns banking | Restart tất cả deployment trong banking |
| Tìm logs lỗi của auth-service-xxx | `kubectl logs` + filter error |
| Phân tích logs apiserver, tìm bất thường | Fetch logs → LLM phân tích |

## Cấu hình

| Env | Mô tả |
|-----|-------|
| `K8S_IN_CLUSTER` | `true` khi chạy trong Pod |
| `PROMETHEUS_URL` | URL Prometheus API |
| `LOKI_URL` | URL Loki |
| `OPENAI_API_KEY` | API key (nếu dùng OpenAI) |
| `OPENAI_BASE_URL` | Base URL (Ollama: `http://ollama:11434/v1`) |
| `OPENAI_MODEL` | Model name |
| `CHROMA_PATH` | Thư mục lưu Chroma DB (default: `/data/chroma`) |
| `RAG_TOP_K` | Số examples RAG retrieve (default: 5) |
| `RAG_ENABLED` | Bật/tắt RAG (default: true) |

### RAG — Thêm example mới

```bash
curl -X POST http://localhost:8080/api/rag/example \
  -H "Content-Type: application/json" \
  -d '{"command": "xem logs auth-service", "intent": {"action": "get_logs", "resource_name": "auth-service"}}'
```

Dữ liệu RAG lưu trong PVC qua StatefulSet `volumeClaimTemplates` (1Gi, storageClassName: nfs-client).
