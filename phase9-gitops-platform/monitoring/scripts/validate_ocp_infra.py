#!/usr/bin/env python3
"""Local validation: Grafana JSON + PrometheusRule YAML (no cluster required)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    import yaml
except ImportError:
    yaml = None


REQUIRED_METRICS = [
    "node_cpu_seconds_total",
    "node_memory_MemAvailable_bytes",
    "node_disk_read_bytes_total",
    "node_disk_reads_completed_total",
    "node_disk_read_time_seconds_total",
    "node_disk_io_time_seconds_total",
    "node_network_receive_bytes_total",
    "kube_node_status_condition",
    "apiserver_request_total",
    "etcd_server_has_leader",
]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    here = Path.cwd()
    ws = ROOT
    for p in [here, *here.parents]:
        if (p / "Open-Source-AIOps-Platform").is_dir():
            ws = p
            break
    grafana = ws / "Open-Source-AIOps-Platform" / "charts" / "grafana" / "dashboards"
    files = [
        "npd-ocp-infra-node-infrastructure.json",
        "npd-ocp-infra-disk-storage.json",
        "npd-ocp-infra-network.json",
        "npd-ocp-infra-openshift-cluster.json",
        "npd-ocp-infra-control-plane-etcd.json",
    ]
    for name in files:
        path = grafana / name
        if not path.exists():
            fail(f"missing {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if "panels" not in data or "templating" not in data:
            fail(f"{name} is not a Grafana dashboard")
        exprs = []
        for p in data["panels"]:
            for t in p.get("targets") or []:
                if t.get("expr"):
                    exprs.append(t["expr"])
        blob = "\n".join(exprs)
        if "clamp_min" not in blob and name.endswith("disk-storage.json"):
            fail("disk dashboard missing clamp_min (divide-by-zero guard)")
        print(f"OK dashboard {name}: {len(data['panels'])} panels, {len(exprs)} queries")

    node_dash = json.loads((grafana / "npd-ocp-infra-node-infrastructure.json").read_text(encoding="utf-8"))
    titles = {p.get("title") for p in node_dash["panels"]}
    for need in ("CPU %", "CPU I/O Wait %", "Memory %"):
        if need not in titles:
            fail(f"node overview missing panel {need!r}")

    rules_dir = ROOT / "manifests" / "prometheusrules" / "platform"
    if yaml is None:
        print("WARN: PyYAML not installed — skip PrometheusRule parse (pip install pyyaml)")
    else:
        for yml in sorted(rules_dir.glob("*.yaml")):
            docs = list(yaml.safe_load_all(yml.read_text(encoding="utf-8")))
            for doc in docs:
                if not doc or doc.get("kind") != "PrometheusRule":
                    continue
                labels = doc.get("metadata", {}).get("labels", {})
                if labels.get("prometheus") != "k8s" or labels.get("role") != "alert-rules":
                    fail(f"{yml.name} missing prometheus=k8s / role=alert-rules (CMO will ignore it)")
                if doc.get("metadata", {}).get("namespace") != "openshift-monitoring":
                    fail(f"{yml.name} must stay in openshift-monitoring")
                groups = doc["spec"]["groups"]
                n = sum(len(g["rules"]) for g in groups)
                for g in groups:
                    for r in g["rules"]:
                        if "alert" in r:
                            if "for" not in r and r["alert"] != "NPDInfraEtcdLeaderChanges":
                                fail(f"{r['alert']} missing for:")
                            if "threshold" not in r.get("annotations", {}):
                                fail(f"{r['alert']} missing annotations.threshold")
                print(f"OK rule {yml.name}: {n} rules")

    print("All local checks passed.")


if __name__ == "__main__":
    main()
