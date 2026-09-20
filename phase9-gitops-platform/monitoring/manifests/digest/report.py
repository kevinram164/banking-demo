#!/usr/bin/env python3
"""NPD cluster status digest → Telegram. Stdlib only."""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

THANOS = os.environ.get(
    "THANOS_URL", "https://thanos-querier.openshift-monitoring.svc:9091"
).rstrip("/")
BOT = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT = os.environ["TELEGRAM_CHAT_ID"]
GRAFANA = os.environ.get(
    "GRAFANA_URL", "https://grafana-aiops-observability.apps.ocp01.npd.co"
)
ICT = timezone(timedelta(hours=7))
CTX = ssl._create_unverified_context()


def token() -> str:
    path = os.environ.get(
        "SA_TOKEN_FILE", "/var/run/secrets/kubernetes.io/serviceaccount/token"
    )
    return open(path, encoding="utf-8").read().strip()


def query(expr: str) -> list[dict]:
    url = THANOS + "/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token()})
    with urllib.request.urlopen(req, context=CTX, timeout=30) as resp:
        body = json.loads(resp.read().decode())
    if body.get("status") != "success":
        raise RuntimeError(body.get("error", "thanos query failed"))
    return body["data"]["result"]


def scalar(expr: str, default: float | None = None) -> float | None:
    try:
        rows = query(expr)
    except Exception:
        return default
    if not rows:
        return default
    try:
        return float(rows[0]["value"][1])
    except (KeyError, IndexError, TypeError, ValueError):
        return default


def fmt(n: float | None, digits: int = 0, suffix: str = "") -> str:
    if n is None:
        return "?"
    if digits == 0:
        return f"{int(round(n))}{suffix}"
    return f"{n:.{digits}f}{suffix}"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def firing_alerts(limit: int = 8) -> list[str]:
    try:
        rows = query(
            "count by (alertname, severity) "
            '(ALERTS{alertstate="firing"} unless ALERTS{alertname="Watchdog"})'
        )
    except Exception:
        return ["(không đọc được ALERTS)"]
    lines = []
    for r in sorted(rows, key=lambda x: -float(x["value"][1]))[:limit]:
        name = r["metric"].get("alertname", "?")
        sev = r["metric"].get("severity", "")
        n = int(float(r["value"][1]))
        extra = f" ×{n}" if n > 1 else ""
        tag = f" [{sev}]" if sev else ""
        lines.append(f"• {esc(name)}{esc(tag)}{extra}")
    return lines


def send(text: str) -> None:
    payload = urllib.parse.urlencode(
        {
            "chat_id": CHAT,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode()
    url = f"https://api.telegram.org/bot{BOT}/sendMessage"
    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def main() -> None:
    now = datetime.now(ICT).strftime("%H:%M %d/%m/%Y")
    ready = scalar('count(kube_node_status_condition{condition="Ready",status="true"}==1)')
    notready = scalar(
        'count(kube_node_status_condition{condition="Ready",status="true"}==0) or vector(0)',
        0,
    )
    cpu = scalar(
        'max(100 * (1 - avg by (instance) '
        '(rate(node_cpu_seconds_total{job="node-exporter",mode="idle"}[5m]))))'
    )
    mem = scalar(
        "max(100 * (1 - (node_memory_MemAvailable_bytes{job=\"node-exporter\"} "
        "/ node_memory_MemTotal_bytes{job=\"node-exporter\"})))"
    )
    disk = scalar(
        "max(100 * (1 - ("
        'node_filesystem_avail_bytes{job="node-exporter",fstype!~"tmpfs|overlay|squashfs"}'
        " / "
        'node_filesystem_size_bytes{job="node-exporter",fstype!~"tmpfs|overlay|squashfs"}'
        ")))"
    )
    run = scalar('sum(kube_pod_status_phase{phase="Running"})')
    pending = scalar('sum(kube_pod_status_phase{phase="Pending"})', 0)
    failed = scalar('sum(kube_pod_status_phase{phase="Failed"})', 0)
    etcd = scalar('min(etcd_server_has_leader{job="etcd"})')
    firing = scalar(
        'count(ALERTS{alertstate="firing"} unless ALERTS{alertname="Watchdog"}) or vector(0)',
        0,
    )
    crit = scalar(
        'count(ALERTS{alertstate="firing",severity="critical"} '
        'unless ALERTS{alertname="Watchdog"}) or vector(0)',
        0,
    )

    if (notready or 0) > 0 or etcd == 0 or (crit or 0) > 0:
        status, emoji = "CRITICAL", "🔴"
    elif (cpu or 0) >= 85 or (mem or 0) >= 90 or (disk or 0) >= 85 or (
        pending or 0
    ) >= 5 or (firing or 0) > 0:
        status, emoji = "WARNING", "🟡"
    else:
        status, emoji = "OK", "🟢"

    etcd_s = "OK" if etcd == 1 else ("NO LEADER" if etcd == 0 else "?")
    nodes = f"{fmt(ready)}/{fmt((ready or 0) + (notready or 0))} Ready"
    if (notready or 0) > 0:
        nodes += f" (NotReady {fmt(notready)})"

    lines = [
        f"{emoji} <b>NPD ocp01 — {now} ICT</b>",
        f"Tình trạng: <b>{status}</b>",
        "",
        f"Nodes: {nodes}",
        f"CPU max: {fmt(cpu, 0, '%')}   RAM max: {fmt(mem, 0, '%')}   Disk max: {fmt(disk, 0, '%')}",
        f"Pods: {fmt(run)} running, {fmt(pending)} pending, {fmt(failed)} failed",
        f"etcd: {etcd_s}",
        f"Alert firing: {fmt(firing)}" + (f" (critical {fmt(crit)})" if (crit or 0) else ""),
    ]
    alerts = firing_alerts()
    if alerts:
        lines.append("")
        lines.append("<b>Alert đang bắn</b>")
        lines.extend(alerts)
    lines += ["", f'<a href="{esc(GRAFANA)}">Grafana NPD</a>']
    send("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400]
        raise SystemExit(f"HTTP {e.code}: {detail}") from e
    except Exception as e:
        # Last-ditch: still try to ping Telegram so silence is not confused with "all OK"
        try:
            send(f"🔴 <b>NPD digest lỗi</b>\n{esc(type(e).__name__)}: {esc(str(e)[:500])}")
        except Exception:
            pass
        raise
