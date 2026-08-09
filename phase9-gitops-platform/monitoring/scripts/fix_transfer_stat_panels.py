"""Fix Grafana transfer stats: total counts, pending=open gauge, colors."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # OCP/
DASH = ROOT / "Open-Source-AIOps-Platform/charts/grafana/dashboards/npd-banking.json"
PHASE8 = (
    ROOT
    / "banking-demo/phase3-monitoring-keda/helm-monitoring/grafana-dashboard-banking-services-phase8.yaml"
)

DS = {"type": "prometheus", "uid": "${datasource}"}

OUTCOME_TOTAL = (
    'round(sum(banking_transfer_outcomes_total{namespace="npd-banking",outcome="%s"}))'
)
PENDING_OPEN = 'max(banking_transfers_pending{namespace="npd-banking"}) or vector(0)'


def color_fixed(hex_color: str) -> dict:
    return {
        "unit": "none",
        "decimals": 0,
        "color": {"mode": "fixed", "fixedColor": hex_color},
        "thresholds": {"mode": "absolute", "steps": [{"color": hex_color, "value": None}]},
    }


def color_threshold_ok_warn(ok: str, warn: str) -> dict:
    """0 = ok color, >0 = warn color."""
    return {
        "unit": "none",
        "decimals": 0,
        "color": {"mode": "thresholds"},
        "thresholds": {
            "mode": "absolute",
            "steps": [
                {"color": ok, "value": None},
                {"color": warn, "value": 1},
            ],
        },
    }


def sync_phase8(dash: dict) -> None:
    body = json.dumps(dash, indent=2, ensure_ascii=False)
    indented = "\n".join(("    " + line if line else "") for line in body.splitlines())
    header = """# Grafana Dashboard — Banking Services (Phase 8)
# Sidecar label: grafana_dashboard=1
# Apply: kubectl apply -f grafana-dashboard-banking-services-phase8.yaml -n monitoring
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboard-banking-services
  labels:
    grafana_dashboard: "1"
  annotations:
    grafana_folder: Banking
data:
  banking-services.json: |
"""
    PHASE8.write_text(header + indented + "\n", encoding="utf-8")


def main() -> None:
    d = json.loads(DASH.read_text(encoding="utf-8"))
    specs = {
        20: ("Transfer — Success (total)", OUTCOME_TOTAL % "success", color_fixed("green")),
        21: ("Transfer — Failed (total)", OUTCOME_TOTAL % "failed", color_threshold_ok_warn("green", "red")),
        22: (
            "Transfer — Pending (open)",
            PENDING_OPEN,
            color_threshold_ok_warn("green", "orange"),
        ),
        23: ("Transfer — Expired (total)", OUTCOME_TOTAL % "expired", color_threshold_ok_warn("green", "yellow")),
        24: ("Transfer — Cancelled (total)", OUTCOME_TOTAL % "cancelled", color_threshold_ok_warn("green", "blue")),
    }
    for p in d.get("panels", []):
        pid = p.get("id")
        if pid not in specs:
            # also catch by title containing Success 1h etc
            title = p.get("title") or ""
            if "Success" in title and "1h" in title:
                pid = 20
            elif "Failed" in title and ("1h" in title or "total" in title.lower()):
                pid = 21
            elif "Pending" in title and ("1h" in title or "open" in title.lower() or "so luong" in title):
                pid = 22
            elif "Expired" in title:
                pid = 23
            elif "Cancelled" in title:
                pid = 24
            else:
                continue
            if pid not in specs:
                continue
        title, expr, fc = specs[pid]
        p["id"] = pid
        p["title"] = title
        p["type"] = "stat"
        if pid == 22:
            p["description"] = (
                "So PENDING dang mo (hold chua confirm/cancel/expire). "
                "Ve 0 khi xu ly xong. Metric: banking_transfers_pending"
            )
        else:
            p["description"] = (
                "Tong outcome tu khi pod transfer-service start "
                "(counter banking_transfer_outcomes_total). Khong phai cua so 1h."
            )
        p["targets"] = [{"expr": expr, "refId": "A", "datasource": DS}]
        p["options"] = {
            "reduceOptions": {"calcs": ["lastNotNull"]},
            "colorMode": "value",
            "graphMode": "none",
        }
        p["fieldConfig"] = {"defaults": fc, "overrides": []}
        print("updated panel", pid, title)

    # also rename % Pending panel description if present
    for p in d.get("panels", []):
        if p.get("id") == 12:
            p["title"] = "Transfer — % Creates still open-ish (rate)"
            p["description"] = (
                "Rate share pending creates (khong phai so dang treo). "
                "Xem panel Pending (open) de biet hang treo hien tai."
            )

    DASH.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sync_phase8(d)
    print("wrote", DASH)
    print("synced", PHASE8)


if __name__ == "__main__":
    main()
