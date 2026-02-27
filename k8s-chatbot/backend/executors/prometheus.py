"""Execute Prometheus PromQL queries."""
import httpx

from config import PROMETHEUS_URL
from agents.parser import CommandIntent


def prometheus_execute(intent: CommandIntent) -> str:
    if not intent.query:
        return "No PromQL query specified"

    try:
        url = f"{PROMETHEUS_URL.rstrip('/')}/api/v1/query"
        params = {"query": intent.query}
        with httpx.Client(timeout=30) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            data = r.json()

        if data.get("status") != "success":
            return f"Prometheus error: {data}"

        results = data.get("data", {}).get("result", [])
        lines = []
        for r in results:
            metric = r.get("metric", {})
            value = r.get("value", [None, None])[1]
            labels = ", ".join(f"{k}={v}" for k, v in metric.items())
            lines.append(f"{labels} => {value}")
        return "\n".join(lines) if lines else "No data"
    except httpx.HTTPError as e:
        return f"Prometheus request failed: {e}"
    except Exception as e:
        return f"Error: {e}"
