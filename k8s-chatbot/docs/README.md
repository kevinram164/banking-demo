# K8s Chatbot — Tài liệu

Chatbot quản lý và trace cụm Kubernetes qua ngôn ngữ tự nhiên.

---

## Mục lục

1. [Tổng quan](#1-tổng-quan)
2. [Kiến trúc](#2-kiến-trúc)
3. [Tính năng](#3-tính-năng)
4. [Cài đặt](#4-cài-đặt)
5. [Cấu hình](#5-cấu-hình)
6. [Sử dụng](#6-sử-dụng)
7. [LLM & Ollama](#7-llm--ollama)
8. [RAG & Học hỏi](#8-rag--học-hỏi)
9. [API Reference](#9-api-reference)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Tổng quan

K8s Chatbot cho phép bạn ra lệnh quản lý cluster Kubernetes bằng ngôn ngữ tự nhiên (tiếng Việt hoặc tiếng Anh), thay vì gõ `kubectl` thủ công.

### Ví dụ

| Bạn nói | Chatbot làm |
|---------|-------------|
| "Check status pods của ns banking" | `kubectl get pods -n banking` |
| "Rollout restart deployment của ns banking" | Restart tất cả deployment trong namespace banking |
| "Tìm logs lỗi của auth-service" | Lấy logs pod auth-service, filter dòng có "error" |
| "Phân tích logs apiserver, tìm bất thường" | Lấy logs → gửi LLM phân tích → trả kết quả |

---

## 2. Kiến trúc

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           K8s Chatbot                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   [User] ──► [Chat UI] ──► [Backend API] ──► [Parser]                       │
│                                    │              │                         │
│                                    │              ├── Rule-based (regex)     │
│                                    │              └── RAG + LLM             │
│                                    │                                         │
│                                    ▼                                         │
│                            [Executor]                                        │
│                                    │                                         │
│              ┌─────────────────────┼─────────────────────┐                  │
│              ▼                     ▼                     ▼                  │
│        [K8s API]             [Loki API]            [Prometheus]               │
│        [Analyzer]            (LogQL)               (PromQL)                  │
│              │                     │                     │                  │
│              │                     │                     │                  │
│              └─────────────────────┼─────────────────────┘                  │
│                                    │                                         │
│                                    ▼                                         │
│                            [LLM: OpenAI / Ollama]                            │
│                            (parse intent, analyze logs)                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Luồng xử lý 1 câu lệnh

1. **User** gửi message qua Chat UI
2. **Parser** hiểu ý:
   - Thử rule-based (regex) trước
   - Nếu không match → RAG retrieve examples tương tự → LLM parse
3. **Executor** thực thi theo intent:
   - `get_pods`, `get_deployments`, `rollout_restart`, `get_logs` → Kubernetes API
   - `analyze_logs` → Fetch logs → Gửi LLM phân tích
   - `logql` → Loki API
   - `promql` → Prometheus API
4. **Response** trả về Chat UI

---

## 3. Tính năng

### 3.1 Kubernetes

| Action | Mô tả | Ví dụ lệnh |
|--------|-------|------------|
| `get_pods` | Liệt kê pods trong namespace | "check pods in banking" |
| `get_deployments` | Liệt kê deployments | "get deployments của ns monitoring" |
| `rollout_restart` | Restart deployment(s) | "rollout restart deployment in banking" |
| `get_logs` | Lấy logs pod | "logs error của auth-service" |

### 3.2 Phân tích logs (analyze_logs)

- Fetch logs từ pod/component
- Gửi logs cho LLM
- LLM phân tích, tìm bất thường/lỗi, đưa khuyến nghị
- **Yêu cầu**: LLM (OpenAI hoặc Ollama)

Ví dụ: "Phân tích logs của apiserver, để xem điểm bất thường của cụm"

### 3.3 Observability

| Action | Nguồn | Ví dụ |
|--------|-------|-------|
| `logql` | Loki | Query LogQL tùy ý |
| `promql` | Prometheus | Query PromQL tùy ý |

### 3.4 RAG (Retrieval Augmented Generation)

- Lưu examples (câu lệnh → intent) trong Chroma vector DB
- Khi parse: retrieve top-k examples tương tự → đưa vào prompt LLM
- Giúp LLM hiểu đúng hơn cách nói của bạn
- Có thể thêm example mới qua API `/api/rag/example`

---

## 4. Cài đặt

### 4.1 Yêu cầu

- Kubernetes cluster (đã có monitoring: Prometheus, Loki)
- (Tùy chọn) LLM: OpenAI API key hoặc Ollama

### 4.2 Chạy local

**Backend:**
```bash
cd k8s-chatbot/backend
pip install -r requirements.txt

export K8S_IN_CLUSTER=false
export OPENAI_BASE_URL=http://localhost:11434/v1   # Ollama
export OPENAI_MODEL=llama3.2

uvicorn main:app --reload --port 8080
```

**Frontend:**
```bash
cd k8s-chatbot/frontend
npm install
npm run dev
```

Truy cập: http://localhost:5173

### 4.3 Deploy lên Kubernetes (Helm)

```bash
# Tạo secret gitlab-registry (nếu chưa có)
kubectl get secret gitlab-registry -n banking -o yaml | \
  sed 's/namespace: banking/namespace: k8s-chatbot/' | \
  grep -v resourceVersion | grep -v uid | kubectl apply -f -

# Cài đặt
helm install k8s-chatbot ./k8s-chatbot/helm -n k8s-chatbot --create-namespace
```

### 4.4 Cấu hình Ollama (không cần OpenAI API key)

```bash
# Cài Ollama trên máy Linux
curl -fsSL https://ollama.com/install.sh | sh

# Tải model
ollama pull llama3.2:3b

# Ollama chạy API tại :11434
```

Trong Helm values:
```yaml
backend:
  openaiBaseUrl: "http://<ollama-host>:11434/v1"
  openaiModel: "llama3.2"
```

---

## 5. Cấu hình

### 5.1 Biến môi trường

| Env | Mô tả | Default |
|-----|-------|---------|
| `K8S_IN_CLUSTER` | Chạy trong Pod (dùng ServiceAccount) | `true` |
| `K8S_NAMESPACE` | Namespace mặc định | `banking` |
| `PROMETHEUS_URL` | URL Prometheus API | `http://kube-prometheus-stack-prometheus.monitoring...` |
| `LOKI_URL` | URL Loki | `http://loki.monitoring...` |
| `TEMPO_URL` | URL Tempo (tracing) | `http://tempo.monitoring...` |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `OPENAI_BASE_URL` | Base URL LLM (Ollama: `http://host:11434/v1`) | — |
| `OPENAI_MODEL` | Tên model | `gpt-4o-mini` |
| `CHROMA_PATH` | Thư mục Chroma DB | `/data/chroma` |
| `RAG_TOP_K` | Số examples RAG retrieve | `5` |
| `RAG_ENABLED` | Bật/tắt RAG | `true` |

### 5.2 Image size

- **~500MB–800MB** (sau khi bỏ sentence-transformers)
- RAG dùng Chroma default embedding (ONNX, nhẹ) thay vì PyTorch

### 5.3 Storage (StatefulSet)

- **volumeClaimTemplates**: `chroma-data` (1Gi)
- **storageClassName**: `nfs-client`
- Dữ liệu RAG (Chroma) lưu persistent

---

## 6. Sử dụng

### 6.1 Ví dụ lệnh

```
Check status pods của ns banking
Rollout restart deployment của ns banking
Tìm logs lỗi của auth-service-xxx
Phân tích logs apiserver, để xem điểm bất thường của cụm
get deployments in monitoring
```

### 6.2 Khi không có LLM

- Rule-based vẫn hoạt động (get_pods, get_logs, rollout_restart, v.v.)
- `analyze_logs` → trả thông báo cần cấu hình LLM
- RAG không dùng được (cần LLM để parse câu phức tạp)

---

## 7. LLM & Ollama

### 7.1 Ollama là gì?

Ollama chạy LLM trên máy của bạn, không cần API key, miễn phí. API tương thích OpenAI.

### 7.2 Luồng dữ liệu khi phân tích logs

```
Kubernetes (logs) ──► k8s-chatbot (fetch) ──► Ollama (nhận prompt chứa logs)
                                                    │
                                                    ▼
                                              Phân tích & trả kết quả
```

- **Ollama không tự lấy data** — chatbot fetch logs từ K8s, đưa vào prompt, gửi cho Ollama
- Ollama chỉ xử lý prompt và sinh ra phân tích

### 7.3 So sánh OpenAI vs Ollama

| | OpenAI API | Ollama |
|---|------------|--------|
| Chi phí | Trả phí | Miễn phí |
| Chạy ở đâu | Cloud | Local |
| Cần API key | Có | Không |
| Bảo mật | Data gửi lên cloud | Data ở local |

---

## 8. RAG & Học hỏi

### 8.1 RAG hoạt động thế nào?

1. Seed examples trong `data/examples.json` (hoặc qua API)
2. Embed examples → lưu Chroma
3. User gửi câu → embed → retrieve top-k tương tự
4. Đưa examples vào prompt LLM → parse chính xác hơn

### 8.2 Thêm example mới

```bash
curl -X POST http://localhost:8080/api/rag/example \
  -H "Content-Type: application/json" \
  -d '{"command": "xem logs auth-service", "intent": {"action": "get_logs", "resource_name": "auth-service"}}'
```

### 8.3 Chatbot có "học" không?

- **Thủ công**: Thêm examples qua API → RAG dùng cho lần sau
- **Tự động**: Chưa có (có thể thêm nút feedback "Đúng/Sai" → auto add)

---

## 9. API Reference

### POST /api/chat

Gửi message, nhận reply.

**Request:**
```json
{"message": "check pods in banking"}
```

**Response:**
```json
{"reply": "NAME\tSTATUS\tREADY\n...", "intent": "get_pods"}
```

### POST /api/rag/example

Thêm example vào RAG.

**Request:**
```json
{
  "command": "phân tích logs apiserver",
  "intent": {"action": "analyze_logs", "resource_name": "apiserver", "namespace": "kube-system"}
}
```

### GET /health

Health check.

---

## 10. Troubleshooting

| Vấn đề | Giải pháp |
|--------|-----------|
| "Cần cấu hình LLM" | Set `OPENAI_API_KEY` hoặc `OPENAI_BASE_URL` (Ollama) |
| Pod không pull được image | Tạo secret `gitlab-registry` trong namespace `k8s-chatbot` |
| "Pod matching X not found" | Kiểm tra namespace, tên pod (apiserver → kube-system) |
| RAG không hoạt động | Kiểm tra PVC mount `/data/chroma`, `RAG_ENABLED=true` |
| Ollama connection refused | Kiểm tra Ollama chạy, URL đúng, network từ Pod tới Ollama |

---

## Cấu trúc thư mục

```
k8s-chatbot/
├── backend/
│   ├── main.py           # FastAPI app
│   ├── config.py
│   ├── agents/parser.py   # Parse intent
│   ├── executors/         # K8s, Loki, Prometheus, Analyzer
│   ├── rag/               # Chroma retriever
│   └── data/examples.json # Seed RAG
├── frontend/              # React chat UI
├── helm/                  # StatefulSet, Service, RBAC
└── docs/                  # Tài liệu
```
