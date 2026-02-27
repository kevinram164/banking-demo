"""
Parse user command → structured intent.
Uses LLM when available, falls back to rule-based.
"""
import json
import re
from dataclasses import dataclass
from typing import Literal

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL


@dataclass
class CommandIntent:
    action: Literal["get_pods", "get_deployments", "rollout_restart", "get_logs", "promql", "logql", "unknown"]
    namespace: str | None = None
    resource_name: str | None = None  # pod name, deployment name
    log_filter: str | None = None  # e.g. "error", "exception"
    log_tail: int = 100
    query: str | None = None  # raw PromQL or LogQL


# Rule-based patterns (fallback when no LLM)
PATTERNS = [
    # get pods
    (r"(?:check|get|list|show|status)\s+(?:status\s+)?pods?\s+(?:in|of|của)\s+(?:ns\s+)?(\w+)", "get_pods", "ns"),
    (r"pods?\s+(?:in|of|của)\s+(?:ns\s+)?(\w+)", "get_pods", "ns"),
    (r"get\s+pods?\s+-n\s+(\w+)", "get_pods", "ns"),
    # get deployments
    (r"(?:check|get|list|show)\s+deployments?\s+(?:in|of|của)\s+(?:ns\s+)?(\w+)", "get_deployments", "ns"),
    (r"deployments?\s+(?:in|of|của)\s+(?:ns\s+)?(\w+)", "get_deployments", "ns"),
    # rollout restart
    (r"rollout\s+restart\s+deployment\s+(?:in|of|của)\s+(?:ns\s+)?(\w+)", "rollout_restart", "ns"),
    (r"rollout\s+restart\s+deployment\s+(\w+)\s+in\s+(\w+)", "rollout_restart", "name_ns"),
    (r"restart\s+(?:deployment\s+)?(\w+)\s+in\s+(\w+)", "rollout_restart", "name_ns"),
    # logs
    (r"logs?\s+(?:lỗi|error)\s+(?:của|of)\s+(\S+)", "get_logs", "pod"),
    (r"logs?\s+(?:của|of)\s+(\S+)(?:\s+.*?(?:error|lỗi))?", "get_logs", "pod"),
    (r"tìm\s+logs?\s+lỗi\s+(?:của|of)\s+(\S+)", "get_logs", "pod"),
]


def _rule_based_parse(text: str) -> CommandIntent | None:
    text = text.strip().lower()
    for pattern, action, capture in PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            if capture == "ns":
                return CommandIntent(action=action, namespace=m.group(1))
            if capture == "name_ns":
                return CommandIntent(action=action, resource_name=m.group(1), namespace=m.group(2))
            if capture == "pod":
                return CommandIntent(action=action, resource_name=m.group(1), log_filter="error")
    return None


def _llm_parse(text: str) -> CommandIntent:
    if not OPENAI_API_KEY and not OPENAI_BASE_URL:
        return CommandIntent(action="unknown")

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=OPENAI_API_KEY or "ollama",
            base_url=OPENAI_BASE_URL or None,
        )
        prompt = f"""Parse this Kubernetes/observability command into JSON. Return ONLY valid JSON, no markdown.

User command: "{text}"

Return JSON with: action, namespace (optional), resource_name (optional), log_filter (optional, e.g. "error"), log_tail (optional, default 100), query (optional, for raw PromQL/LogQL).

Valid actions: get_pods, get_deployments, rollout_restart, get_logs, promql, logql, unknown

Examples:
- "check pods in banking" → {{"action":"get_pods","namespace":"banking"}}
- "rollout restart deployment in banking" → {{"action":"rollout_restart","namespace":"banking"}}
- "logs error of auth-service-xxx" → {{"action":"get_logs","resource_name":"auth-service-xxx","log_filter":"error"}}
- "CPU usage of auth-service" → {{"action":"promql","query":"rate(container_cpu_usage_seconds_total{{container=~\"auth-service\"}}[5m])"}}
"""
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = resp.choices[0].message.content.strip()
        # Remove markdown code block if present
        if content.startswith("```"):
            content = re.sub(r"^```\w*\n?", "", content).rstrip("`")
        data = json.loads(content)
        return CommandIntent(
            action=data.get("action", "unknown"),
            namespace=data.get("namespace"),
            resource_name=data.get("resource_name"),
            log_filter=data.get("log_filter"),
            log_tail=int(data.get("log_tail", 100)),
            query=data.get("query"),
        )
    except Exception:
        return CommandIntent(action="unknown")


def parse_command(text: str) -> CommandIntent:
    """Parse user command. Try rule-based first, then LLM."""
    intent = _rule_based_parse(text)
    if intent:
        return intent
    return _llm_parse(text)
