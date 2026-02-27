"""Execute Loki LogQL queries."""
import httpx
from urllib.parse import quote

from config import LOKI_URL
from agents.parser import CommandIntent


def _build_logql(intent: CommandIntent) -> str:
    if intent.query:
        return intent.query
    # Build from intent
    parts = []
    if intent.namespace:
        parts.append(f'{{namespace="{intent.namespace}"}}')
    else:
        parts.append("{}")
    if intent.resource_name:
        # Pod name can be partial (e.g. auth-service-xxx)
        parts[0] = parts[0].rstrip("}") + f',pod=~"{intent.resource_name}.*"}}'
    if intent.log_filter:
        parts.append(f'|~ "(?i){intent.log_filter}"')
    return "".join(parts)


def loki_execute(intent: CommandIntent) -> str:
    logql = _build_logql(intent)
    limit = intent.log_tail

    try:
        url = f"{LOKI_URL.rstrip('/')}/loki/api/v1/query_range"
        params = {"query": logql, "limit": limit}
        with httpx.Client(timeout=30) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            data = r.json()

        if data.get("status") != "success":
            return f"Loki error: {data}"

        streams = data.get("data", {}).get("result", [])
        lines = []
        for s in streams:
            labels = s.get("stream", {})
            for v in s.get("values", []):
                ts, log = v[0], v[1]
                lines.append(f"[{labels.get('pod', '?')}] {log}")

        if not lines:
            return f"No logs found for query: {logql}"
        return "\n".join(lines[-limit:])  # respect limit
    except httpx.HTTPError as e:
        return f"Loki request failed: {e}"
    except Exception as e:
        return f"Error: {e}"
