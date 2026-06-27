#!/usr/bin/env bash
# Copy banking ArgoCD apps từ template chung, set targetRevision=dev-ocp
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/phase9-gitops-platform/gitops-platform/applications/banking"
DST="$ROOT/phase9-gitops-platform/environments/dev-ocp/argocd/applications/banking"

mkdir -p "$DST"
for f in "$SRC"/*.yaml; do
  name="$(basename "$f")"
  sed 's/targetRevision: main/targetRevision: dev-ocp/g' "$f" > "$DST/$name"
done
echo "Generated $(ls -1 "$DST" | wc -l) files in $DST"
