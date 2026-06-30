#!/usr/bin/env bash
# SCC theo namespace — patch UID vào dải openshift.io/sa.scc.uid-range + gán nonroot cho cả NS
# Thay cho anyuid/privileged (lab) hoặc custom SCC từng SA.
#
# Usage:
#   ./namespace-scc-setup.sh argocd
#   ./namespace-scc-setup.sh platform
#   ./namespace-scc-setup.sh argocd --keep-dex
#
# Cần cluster-admin.
set -euo pipefail

NS="${1:-}"
KEEP_DEX=false
shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep-dex) KEEP_DEX=true ;;
    -h|--help)
      echo "Usage: $0 <namespace> [--keep-dex]"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
  shift
done

if [[ -z "$NS" ]]; then
  echo "Usage: $0 <namespace> [--keep-dex]"
  exit 1
fi

if ! oc get ns "$NS" &>/dev/null; then
  echo "Namespace $NS not found"
  exit 1
fi

UID_RANGE=$(oc get ns "$NS" -o jsonpath='{.metadata.annotations.openshift\.io/sa\.scc\.uid-range}')
if [[ -z "$UID_RANGE" ]]; then
  echo "ERROR: namespace $NS has no openshift.io/sa.scc.uid-range annotation"
  exit 1
fi

MIN_UID="${UID_RANGE%%/*}"
SPAN="${UID_RANGE##*/}"
MAX_UID=$((MIN_UID + SPAN - 1))

echo "==> Namespace: $NS"
echo "    UID range: $MIN_UID – $MAX_UID ($UID_RANGE)"

uid_in_range() {
  local uid="$1"
  [[ -z "$uid" || "$uid" == "null" ]] && return 0
  [[ "$uid" -ge "$MIN_UID" && "$uid" -le "$MAX_UID" ]]
}

patch_workload_uid() {
  local kind="$1" name="$2"

  if [[ "$name" == harbor-* ]]; then
    echo "  skip $kind/$name (Harbor UID 999/10000 — dùng harbor-scc-setup.sh)"
    return 0
  fi

  local pod_uid
  pod_uid=$(oc get "$kind" "$name" -n "$NS" -o jsonpath='{.spec.template.spec.securityContext.runAsUser}' 2>/dev/null || true)

  if uid_in_range "$pod_uid"; then
    echo "  skip $kind/$name (pod runAsUser=$pod_uid OK)"
    return 0
  fi

  echo "  patch $kind/$name runAsUser ${pod_uid:-<unset>} -> $MIN_UID"
  oc patch "$kind" "$name" -n "$NS" --type='json' -p="[
    {\"op\":\"add\",\"path\":\"/spec/template/spec/securityContext\",\"value\":{
      \"runAsUser\":$MIN_UID,\"runAsGroup\":$MIN_UID,\"fsGroup\":$MIN_UID,\"runAsNonRoot\":true
    }}
  ]" 2>/dev/null || oc patch "$kind" "$name" -n "$NS" --type='json' -p="[
    {\"op\":\"replace\",\"path\":\"/spec/template/spec/securityContext/runAsUser\",\"value\":$MIN_UID},
    {\"op\":\"replace\",\"path\":\"/spec/template/spec/securityContext/runAsGroup\",\"value\":$MIN_UID},
    {\"op\":\"replace\",\"path\":\"/spec/template/spec/securityContext/fsGroup\",\"value\":$MIN_UID},
    {\"op\":\"replace\",\"path\":\"/spec/template/spec/securityContext/runAsNonRoot\",\"value\":true}
  ]"

  # Container-level runAsUser (redis, dex, jenkins, …)
  local -a cnames=()
  mapfile -t cnames < <(oc get "$kind" "$name" -n "$NS" -o jsonpath='{range .spec.template.spec.containers[*]}{.name}{"\n"}{end}' 2>/dev/null || true)
  local i cuid
  for i in "${!cnames[@]}"; do
    cuid=$(oc get "$kind" "$name" -n "$NS" -o jsonpath="{.spec.template.spec.containers[$i].securityContext.runAsUser}")
    if ! uid_in_range "$cuid"; then
      oc patch "$kind" "$name" -n "$NS" --type='json' -p="[
        {\"op\":\"add\",\"path\":\"/spec/template/spec/containers/$i/securityContext\",\"value\":{\"runAsUser\":$MIN_UID,\"runAsGroup\":$MIN_UID,\"runAsNonRoot\":true}}
      ]" 2>/dev/null || oc patch "$kind" "$name" -n "$NS" --type='json' -p="[
        {\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/$i/securityContext/runAsUser\",\"value\":$MIN_UID},
        {\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/$i/securityContext/runAsGroup\",\"value\":$MIN_UID}
      ]" 2>/dev/null || true
    fi
  done
}

echo "==> Patch Deployments / StatefulSets to namespace UID range"
for kind in deployment statefulset; do
  while read -r name; do
    [[ -z "$name" ]] && continue
    patch_workload_uid "$kind" "$name"
  done < <(oc get "$kind" -n "$NS" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null || true)
done

if [[ "$NS" == "argocd" && "$KEEP_DEX" == "false" ]]; then
  if oc get deployment argocd-dex-server -n "$NS" &>/dev/null; then
    echo "==> Scale argocd-dex-server to 0 (SSO không dùng — tránh seccomp/privileged)"
    echo "    Dùng --keep-dex nếu cần Dex + patch thủ công"
    oc scale deployment argocd-dex-server -n "$NS" --replicas=0
  fi
fi

echo "==> Gỡ anyuid / privileged khỏi namespace (nếu có)"
oc adm policy remove-scc-from-group anyuid "system:serviceaccounts:${NS}" 2>/dev/null || true
oc adm policy remove-scc-from-group privileged "system:serviceaccounts:${NS}" 2>/dev/null || true

echo "==> Gán SCC nonroot cho toàn bộ ServiceAccount trong namespace"
oc adm policy add-scc-to-group nonroot "system:serviceaccounts:${NS}"

echo "==> Restart workloads"
oc rollout restart deployment,statefulset -n "$NS" 2>/dev/null || true

echo ""
echo "Done. Kiểm tra:"
echo "  watch oc get pods -n $NS"
echo "  ./phase9-gitops-platform/environments/dev-ocp/scripts/discover-pod-scc.sh $NS"
echo ""
echo "Namespaces Phase 9 thường cần:"
echo "  ./namespace-scc-setup.sh argocd"
echo "  ./harbor-scc-setup.sh              # Harbor — trước hoặc sau namespace-scc-setup platform"
echo "  ./namespace-scc-setup.sh platform  # Jenkins (bỏ qua harbor-*)"
echo "  ./namespace-scc-setup.sh vault"
