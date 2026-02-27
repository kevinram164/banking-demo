"""
Parse user command → structured intent.
Uses rule-based first, then RAG+LLM when available.
"""
import json
import re
from dataclasses import dataclass
from typing import Literal

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL


@dataclass
class CommandIntent:
    action: Literal["get_pods", "get_deployments", "rollout_restart", "get_logs", "analyze_logs", "promql", "logql", "unknown"]
    namespace: str | None = None
    resource_name: str | None = None  # pod name, deployment name
    log_filter: str | None = None  # e.g. "error", "exception"
    log_tail: int = 100
    query: str | None = None  # raw PromQL or LogQL
    analysis_goal: str | None = None  # e.g. "điểm bất thường", "anomalies"


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
    # analyze_logs
    (r"phân\s+tích\s+logs?\s+(?:của|of)\s+(\S+)", "analyze_logs", "pod"),
    (r"analyze\s+logs?\s+(?:của|of)\s+(\S+)", "analyze_logs", "pod"),
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
                if action == "analyze_logs":
                    return CommandIntent(action=action, resource_name=m.group(1), log_tail=500, analysis_goal="điểm bất thường")
                return CommandIntent(action=action, resource_name=m.group(1), log_filter="error")
    return None


def _build_rag_examples(text: str) -> str:
    """Retrieve similar examples from RAG for prompt context."""
    try:
        from rag import retrieve_examples
        examples = retrieve_examples(text)
        if not examples:
            return ""
        lines = []
        for ex in examples:
            lines.append(f'- "{ex["command"]}" → {json.dumps(ex["intent"])}')
        return "\n".join(lines)
    except Exception:
        return ""


def _llm_parse(text: str) -> CommandIntent:
    if not OPENAI_API_KEY and not OPENAI_BASE_URL:
        return CommandIntent(action="unknown")

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=OPENAI_API_KEY or "ollama",
            base_url=OPENAI_BASE_URL or None,
        )
        rag_examples = _build_rag_examples(text)
        examples_block = rag_examples if rag_examples else """- "check pods in banking" → {"action":"get_pods","namespace":"banking"}
- "rollout restart deployment in banking" → {"action":"rollout_restart","namespace":"banking"}
- "logs error of auth-service-xxx" → {"action":"get_logs","resource_name":"auth-service-xxx","log_filter":"error"}"""

        prompt = f"""Parse this Kubernetes/observability command into JSON. Return ONLY valid JSON, no markdown.

User command: "{text}"

Return JSON with: action, namespace (optional), resource_name (optional), log_filter (optional), log_tail (optional, default 500 for analyze_logs), query (optional), analysis_goal (optional, for analyze_logs: "điểm bất thường", "anomalies", "lỗi").

Valid actions: get_pods, get_deployments, rollout_restart, get_logs, analyze_logs, promql, logql, unknown

analyze_logs: khi user muốn PHÂN TÍCH logs (tìm bất thường, lỗi, vấn đề). Cần resource_name (pod/component), namespace (apiserver→kube-system), analysis_goal (optional).

Similar examples (use as reference):
{examples_block}
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
        tail = 500 if data.get("action") == "analyze_logs" else int(data.get("log_tail", 100))
        return CommandIntent(
            action=data.get("action", "unknown"),
            namespace=data.get("namespace"),
            resource_name=data.get("resource_name"),
            log_filter=data.get("log_filter"),
            log_tail=tail,
            query=data.get("query"),
            analysis_goal=data.get("analysis_goal"),
        )
    except Exception:
        return CommandIntent(action="unknown")


def parse_command(text: str) -> CommandIntent:
    """Parse user command. Try rule-based first, then LLM."""
    intent = _rule_based_parse(text)
    if intent:
        return intent
    return _llm_parse(text)
