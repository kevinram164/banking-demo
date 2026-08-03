"""Port Phase 3 Grafana dashboards → AIOps NPD folder (OCP namespaces/jobs)."""
from __future__ import annotations

import copy
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]  # OCP/
# script lives in banking-demo/.../monitoring/scripts → parents[3]=banking-demo? 
# Better: locate from cwd or absolute


def find_root() -> pathlib.Path:
    here = pathlib.Path.cwd()
    for p in [here, *here.parents]:
        if (p / "banking-demo").is_dir() and (p / "Open-Source-AIOps-Platform").is_dir():
            return p
        if (p / "phase3-monitoring-keda").is_dir():
            # inside banking-demo
            return p.parent
    raise SystemExit("Run from OCP workspace root")


def extract_json_from_cm(path: pathlib.Path) -> tuple[str, dict]:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"([a-zA-Z0-9_.-]+\.json):\s*\|\s*\n", text)
    if not m:
        raise SystemExit(f"fail extract {path}")
    fname = m.group(1)
    after = text.split(fname + ": |", 1)[1].lstrip("\n")
    lines = after.splitlines()
    ind = len(lines[0]) - len(lines[0].lstrip(" "))
    body_lines = []
    for line in lines:
        if line.strip() and (len(line) - len(line.lstrip(" "))) < ind:
            break
        body_lines.append(line[ind:] if len(line) >= ind else line)
    return fname, json.loads("\n".join(body_lines).strip())


JOB_BANK = (
    ".*auth-service.*|.*account-service.*|.*transfer-service.*"
    "|.*notification-service.*|.*api-producer.*|.*shop-bridge.*|banking-.*"
)
JOB_SHOP = (
    ".*gateway.*|.*order-service.*|.*catalog-service.*"
    "|.*auth-service.*|.*payment-worker.*|npd-shop.*"
)


def patch_expr(expr: str, namespace: str, job_re: str) -> str:
    def repl_job_eq(m: re.Match) -> str:
        name = m.group(1)
        return f'namespace="{namespace}",job=~".*{re.escape(name)}.*"'

    def repl_job_re(_: re.Match) -> str:
        return f'namespace="{namespace}",job=~"{job_re}"'

    e = re.sub(r'job="([^"]+)"', repl_job_eq, expr)
    e = re.sub(r'job=~"[^"]+"', repl_job_re, e)
    for prefix in (
        "http_requests_total{",
        "http_request_duration_seconds_bucket{",
        "http_request_duration_seconds_count{",
        "http_request_duration_seconds_sum{",
    ):
        if prefix not in e:
            continue
        inside = e.split(prefix, 1)[1].split("}", 1)[0]
        if f'namespace="{namespace}"' not in inside:
            e = e.replace(prefix, f'{prefix}namespace="{namespace}",', 1)
    return e


def patch_dashboard(
    d: dict,
    title: str,
    uid: str,
    tags: list[str],
    namespace: str,
    job_re: str,
) -> dict:
    d = copy.deepcopy(d)
    d["title"] = title
    d["uid"] = uid
    d["tags"] = tags
    d["templating"] = {
        "list": [
            {
                "name": "datasource",
                "type": "datasource",
                "query": "prometheus",
                "current": {"text": "Prometheus", "value": "Prometheus"},
                "hide": 0,
            }
        ]
    }
    for p in d.get("panels", []):
        p["datasource"] = {"type": "prometheus", "uid": "${datasource}"}
        for t in p.get("targets", []):
            if "expr" in t:
                t["expr"] = patch_expr(t["expr"], namespace, job_re)
            t["datasource"] = {"type": "prometheus", "uid": "${datasource}"}
    return d


def shop_from_banking(bank: dict) -> dict:
    d = copy.deepcopy(bank)
    for p in d.get("panels", []):
        title = p.get("title", "")
        title = (
            title.replace("Auth Service", "Gateway")
            .replace("Account Service", "Order")
            .replace("Transfer Service", "Catalog")
            .replace("Notification Service", "Payment")
            .replace("Transfer —", "Order API —")
            .replace("Banking", "Shop")
        )
        p["title"] = title
    d = patch_dashboard(
        d,
        "NPD Shop Services",
        "npd-shop-services",
        ["npd", "shop", "http"],
        "npd-shop",
        JOB_SHOP,
    )
    for p in d.get("panels", []):
        for t in p.get("targets", []):
            if "expr" not in t:
                continue
            e = t["expr"]
            e = e.replace("/api/auth.*", "/api/.*")
            e = e.replace("/api/account.*", "/api/orders.*")
            e = e.replace("/api/transfer.*", "/api/orders.*|/api/payments.*")
            e = e.replace("/api/notifications.*", "/api/payments.*")
            e = e.replace("/transfer|/api/transfer.*", "/api/orders.*|/api/payments.*")
            t["expr"] = e
    return d


def main() -> None:
    root = find_root()
    base = root / "banking-demo/phase3-monitoring-keda/helm-monitoring"
    out = root / "Open-Source-AIOps-Platform/charts/grafana/dashboards"
    out.mkdir(parents=True, exist_ok=True)

    _, banking = extract_json_from_cm(base / "grafana-dashboard-banking-services-phase8.yaml")
    _, kong = extract_json_from_cm(base / "grafana-dashboard-kong.yaml")
    _, rabbit = extract_json_from_cm(base / "grafana-dashboard-rabbitmq.yaml")

    files = {
        "npd-banking.json": patch_dashboard(
            banking,
            "NPD Banking Services",
            "npd-banking-services",
            ["npd", "banking", "http", "phase8"],
            "npd-banking",
            JOB_BANK,
        ),
        "npd-shop.json": shop_from_banking(banking),
        "npd-kong.json": patch_dashboard(
            kong,
            "NPD Kong Gateway",
            "npd-kong",
            ["npd", "kong", "infra"],
            "kong",
            ".*kong.*",
        ),
        "npd-rabbitmq.json": patch_dashboard(
            rabbit,
            "NPD RabbitMQ",
            "npd-rabbitmq",
            ["npd", "rabbitmq", "infra"],
            "rabbit",
            ".*rabbit.*",
        ),
    }
    for name, data in files.items():
        path = out / name
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"wrote {path.relative_to(root)} panels={len(data['panels'])}")


if __name__ == "__main__":
    main()
