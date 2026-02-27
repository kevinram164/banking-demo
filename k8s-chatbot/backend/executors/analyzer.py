"""
Analyze logs via LLM - fetch logs then ask LLM to analyze.
"""
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from agents.parser import CommandIntent
from executors.k8s import k8s_execute

# Giới hạn chars gửi cho LLM (~4k tokens)
MAX_LOG_CHARS = 12000


def _fetch_logs(intent: CommandIntent) -> str:
    """Fetch logs using get_logs logic."""
    log_intent = CommandIntent(
        action="get_logs",
        namespace=intent.namespace or ("kube-system" if intent.resource_name and "apiserver" in intent.resource_name.lower() else None),
        resource_name=intent.resource_name,
        log_filter=intent.log_filter,
        log_tail=intent.log_tail,
    )
    return k8s_execute(log_intent)


def _llm_analyze(logs: str, goal: str | None, resource_name: str) -> str:
    if not OPENAI_API_KEY and not OPENAI_BASE_URL:
        return "Cần cấu hình LLM (OPENAI_API_KEY hoặc OPENAI_BASE_URL) để phân tích logs."

    goal_text = goal or "điểm bất thường, lỗi, cảnh báo"
    if len(logs) > MAX_LOG_CHARS:
        logs = logs[:MAX_LOG_CHARS] + "\n\n[... truncated ...]"

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=OPENAI_API_KEY or "ollama",
            base_url=OPENAI_BASE_URL or None,
        )
        prompt = f"""Phân tích các log sau của {resource_name}. Tìm {goal_text}.

Logs:
```
{logs}
```

Trả về phân tích bằng tiếng Việt, gồm:
1. Tóm tắt ngắn
2. Các điểm bất thường / lỗi / cảnh báo (nếu có)
3. Khuyến nghị (nếu cần)
"""
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Lỗi khi phân tích: {e}"


def analyze_logs_execute(intent: CommandIntent) -> str:
    """Fetch logs → LLM analyze → return."""
    if not intent.resource_name:
        return "Vui lòng chỉ rõ pod/component cần phân tích (ví dụ: apiserver, auth-service)."

    logs = _fetch_logs(intent)
    if "not found" in logs.lower() or ("please specify" in logs.lower()):
        return logs

    return _llm_analyze(logs, intent.analysis_goal, intent.resource_name)
