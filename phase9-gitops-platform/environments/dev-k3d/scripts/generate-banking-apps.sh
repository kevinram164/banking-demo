#!/usr/bin/env bash
# Copy banking ArgoCD apps từ template chung, set targetRevision=dev-k3d
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/phase9-gitops-platform/argocd/applications/banking"
DST="$ROOT/phase9-gitops-platform/environments/dev-k3d/argocd/applications/banking"

mkdir -p "$DST"
for f in "$SRC"/*.yaml; do
  name="$(basename "$f")"
  sed 's/targetRevision: main/targetRevision: dev-k3d/g' "$f" > "$DST/$name"
done
echo "Generated $(ls -1 "$DST" | wc -l) files in $DST"
