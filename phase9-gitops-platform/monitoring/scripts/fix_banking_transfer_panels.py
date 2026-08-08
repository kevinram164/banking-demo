"""Fix NPD Banking dashboard transfer queries for OCP label shapes + business outcomes."""
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
    # Prefer dedicated updater for outcome panels
    from update_transfer_outcome_panels import main as update_outcomes

    update_outcomes()

    d = json.loads(path.read_text(encoding="utf-8"))
    for p in d.get("panels", []):
        for t in p.get("targets", []):
            if "expr" in t and "banking_transfer_outcomes_total" not in t["expr"]:
                t["expr"] = clean(t["expr"])
    path.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("updated", path)


if __name__ == "__main__":
    main()
