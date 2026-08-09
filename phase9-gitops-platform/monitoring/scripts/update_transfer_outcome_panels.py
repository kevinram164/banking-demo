"""Update npd-banking Grafana panels for business transfer outcomes."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # OCP/
DASH = ROOT / "Open-Source-AIOps-Platform/charts/grafana/dashboards/npd-banking.json"

DS = {"type": "prometheus", "uid": "${datasource}"}

OUTCOME_RATE = (
    'sum(rate(banking_transfer_outcomes_total{namespace="npd-banking",outcome="%s"}[5m]))'
)
OUTCOME_TOTAL = (
    'round(sum(banking_transfer_outcomes_total{namespace="npd-banking",outcome="%s"}))'
)
PENDING_OPEN = 'max(banking_transfers_pending{namespace="npd-banking"}) or vector(0)'


def target(expr: str, legend: str, ref: str) -> dict:
    return {
        "expr": expr,
        "legendFormat": legend,
        "refId": ref,
        "datasource": DS,
    }


def main() -> None:
    d = json.loads(DASH.read_text(encoding="utf-8"))
    panels = d.get("panels", [])

    # Replace transfer HTTP success/fail panels (id 10-12)
    for p in panels:
        pid = p.get("id")
        if pid == 10:
            p["title"] = "Transfer — Nghiep vu (outcome RPS)"
            p["description"] = (
                "Business outcomes from transfer-service: "
                "success / failed / pending / expired / cancelled "
                "(NOT HTTP 2xx). Metric: banking_transfer_outcomes_total"
            )
            p["targets"] = [
                target(OUTCOME_RATE % "success", "Success", "A"),
                target(OUTCOME_RATE % "failed", "Failed", "B"),
                target(OUTCOME_RATE % "pending", "Pending", "C"),
                target(OUTCOME_RATE % "expired", "Expired", "D"),
                target(OUTCOME_RATE % "cancelled", "Cancelled", "E"),
            ]
            p["fieldConfig"] = {"defaults": {"unit": "reqps"}, "overrides": []}
        elif pid == 11:
            p["title"] = "Transfer — % Settle success"
            p["description"] = (
                "success / (success+failed+expired+cancelled). Pending excluded."
            )
            p["targets"] = [
                {
                    "expr": (
                        '100 * sum(rate(banking_transfer_outcomes_total{namespace="npd-banking",outcome="success"}[5m])) / '
                        'clamp_min(sum(rate(banking_transfer_outcomes_total{namespace="npd-banking",'
                        'outcome=~"success|failed|expired|cancelled"}[5m])), 1e-9)'
                    ),
                    "refId": "A",
                    "datasource": DS,
                }
            ]
        elif pid == 12:
            p["title"] = "Transfer — % Pending (of creates)"
            p["description"] = (
                "pending / (pending+success+failed+expired+cancelled) rate share. "
                "High pending = create without confirm."
            )
            p["targets"] = [
                {
                    "expr": (
                        '100 * sum(rate(banking_transfer_outcomes_total{namespace="npd-banking",outcome="pending"}[5m])) / '
                        'clamp_min(sum(rate(banking_transfer_outcomes_total{namespace="npd-banking"}[5m])), 1e-9)'
                    ),
                    "refId": "A",
                    "datasource": DS,
                }
            ]

    # Add outcome counters row if not present
    if not any(p.get("id") == 20 for p in panels):
        y = max((p.get("gridPos", {}).get("y", 0) + p.get("gridPos", {}).get("h", 0)) for p in panels)
        outcomes = [
            ("success", "Success (total)", 20, 0),
            ("failed", "Failed (total)", 21, 4),
            ("pending", "Pending (open)", 22, 8),
            ("expired", "Expired (total)", 23, 12),
            ("cancelled", "Cancelled (total)", 24, 16),
        ]
        for outcome, title, pid, x in outcomes:
            expr = PENDING_OPEN if outcome == "pending" else (OUTCOME_TOTAL % outcome)
            panels.append(
                {
                    "id": pid,
                    "type": "stat",
                    "title": f"Transfer — {title}",
                    "gridPos": {"x": x if x < 20 else 20, "y": y, "w": 4 if x < 20 else 4, "h": 4},
                    "targets": [
                        {
                            "expr": expr,
                            "refId": "A",
                            "datasource": DS,
                        }
                    ],
                    "options": {
                        "reduceOptions": {"calcs": ["lastNotNull"]},
                        "colorMode": "value",
                        "graphMode": "none",
                    },
                    "fieldConfig": {
                        "defaults": {
                            "unit": "none",
                            "decimals": 0,
                            "color": {"mode": "fixed", "fixedColor": "green"}
                            if outcome == "success"
                            else {"mode": "thresholds"},
                            "thresholds": {
                                "mode": "absolute",
                                "steps": [
                                    {"color": "green", "value": None},
                                    {
                                        "color": (
                                            "orange"
                                            if outcome == "pending"
                                            else "red"
                                            if outcome == "failed"
                                            else "yellow"
                                            if outcome == "expired"
                                            else "blue"
                                        ),
                                        "value": 1,
                                    },
                                ],
                            },
                        },
                        "overrides": [],
                    },
                }
            )
        # fix x positions properly: 0,4,8,12,16 for 5 panels of w=4
        for i, (_, _, pid, _) in enumerate(outcomes):
            for p in panels:
                if p.get("id") == pid:
                    p["gridPos"] = {"x": i * 4, "y": y, "w": 4 if i < 4 else 4, "h": 4}
                    if i == 4:
                        p["gridPos"] = {"x": 16, "y": y, "w": 8, "h": 4}

    d["panels"] = panels
    DASH.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("updated", DASH)


if __name__ == "__main__":
    main()
