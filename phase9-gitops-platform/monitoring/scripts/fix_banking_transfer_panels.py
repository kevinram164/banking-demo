"""Fix NPD Banking dashboard transfer queries for OCP label shapes."""
from __future__ import annotations

import json
import re
from pathlib import Path


def find_root() -> Path:
    here = Path.cwd()
    for p in [here, *here.parents]:
        if (p / "Open-Source-AIOps-Platform").is_dir() and (p / "banking-demo").is_dir():
            return p
    raise SystemExit("run from OCP workspace")


def clean(expr: str) -> str:
    e = expr
    e = re.sub(r'namespace="npd-banking",\s*namespace="npd-banking"', 'namespace="npd-banking"', e)
    e = re.sub(r',?job=~"[^"]*"', "", e)
    e = e.replace('endpoint=~"/transfer|/api/transfer.*"', 'endpoint=~".*transfer.*"')
    e = e.replace('endpoint=~"/api/auth.*"', 'endpoint=~".*auth.*"')
    e = e.replace('endpoint=~"/api/account.*"', 'endpoint=~".*account.*"')
    e = e.replace('endpoint=~"/api/notifications.*"', 'endpoint=~".*notif.*"')
    e = re.sub(r"\{\s*,", "{", e)
    e = re.sub(r",\s*,", ",", e)
    e = re.sub(r",\s*}", "}", e)
    return e


def main() -> None:
    root = find_root()
    path = root / "Open-Source-AIOps-Platform/charts/grafana/dashboards/npd-banking.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    ds = {"type": "prometheus", "uid": "${datasource}"}

    for p in d.get("panels", []):
        for t in p.get("targets", []):
            if "expr" in t:
                t["expr"] = clean(t["expr"])

        title = p.get("title", "")
        if "Tỷ lệ thành công" in title:
            p["targets"] = [
                {
                    "expr": (
                        '100 * sum(rate(http_requests_total{namespace="npd-banking",'
                        'endpoint=~".*transfer.*",status=~"2.."}[5m])) / '
                        'clamp_min(sum(rate(http_requests_total{namespace="npd-banking",'
                        'endpoint=~".*transfer.*"}[5m])), 1e-9)'
                    ),
                    "refId": "A",
                    "datasource": ds,
                }
            ]
        elif "Tỷ lệ thất bại" in title:
            p["targets"] = [
                {
                    "expr": (
                        '100 * sum(rate(http_requests_total{namespace="npd-banking",'
                        'endpoint=~".*transfer.*",status=~"[45].."}[5m])) / '
                        'clamp_min(sum(rate(http_requests_total{namespace="npd-banking",'
                        'endpoint=~".*transfer.*"}[5m])), 1e-9)'
                    ),
                    "refId": "A",
                    "datasource": ds,
                }
            ]
        elif "Giao dịch thành công vs thất bại" in title:
            p["targets"] = [
                {
                    "expr": 'sum(rate(http_requests_total{namespace="npd-banking",endpoint=~".*transfer.*",status=~"2.."}[5m]))',
                    "legendFormat": "OK 2xx",
                    "refId": "A",
                    "datasource": ds,
                },
                {
                    "expr": 'sum(rate(http_requests_total{namespace="npd-banking",endpoint=~".*transfer.*",status=~"4.."}[5m]))',
                    "legendFormat": "Client 4xx",
                    "refId": "B",
                    "datasource": ds,
                },
                {
                    "expr": 'sum(rate(http_requests_total{namespace="npd-banking",endpoint=~".*transfer.*",status=~"5.."}[5m]))',
                    "legendFormat": "Server 5xx",
                    "refId": "C",
                    "datasource": ds,
                },
            ]

    path.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("updated", path)


if __name__ == "__main__":
    main()
