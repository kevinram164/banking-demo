import os

# Kubernetes - in-cluster config khi chạy trong Pod
K8S_IN_CLUSTER = os.getenv("K8S_IN_CLUSTER", "true").lower() == "true"
K8S_NAMESPACE = os.getenv("K8S_NAMESPACE", "banking")

# Observability stack (trong cluster)
PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090",
)
LOKI_URL = os.getenv(
    "LOKI_URL",
    "http://loki.monitoring.svc.cluster.local:3100",
)
TEMPO_URL = os.getenv(
    "TEMPO_URL",
    "http://tempo.monitoring.svc.cluster.local:3200",
)

# LLM - OpenAI API (hoặc compatible: Ollama, OpenRouter, etc.)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")  # e.g. http://ollama:11434/v1
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

# RAG - Chroma vector DB
CHROMA_PATH = os.getenv("CHROMA_PATH", "/data/chroma")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() == "true"
