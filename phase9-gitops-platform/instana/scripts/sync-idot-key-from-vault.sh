#!/usr/bin/env bash
# Vault → ESO Secret → patch Argo helm.parameters.instanaKey (không commit key vào git).
# Lý do: OCP GitOps multi-source không đưa valuesFrom Secret vào `helm template`.
set -euo pipefail

APP=observability-instana-otel-collector
KEY="$(oc -n observability get secret instana-otlp-credentials -o jsonpath='{.data.key}' | base64 -d)"
[[ -n "$KEY" ]] || { echo "ERROR: secret observability/instana-otlp-credentials missing key" >&2; exit 1; }

oc -n argocd patch app "$APP" --type json -p "[
  {\"op\":\"add\",\"path\":\"/spec/sources/0/helm/parameters\",\"value\":[{\"name\":\"instanaKey\",\"value\":\"${KEY}\"}]}
]" 2>/dev/null || \
oc -n argocd patch app "$APP" --type json -p "[
  {\"op\":\"replace\",\"path\":\"/spec/sources/0/helm/parameters\",\"value\":[{\"name\":\"instanaKey\",\"value\":\"${KEY}\"}]}
]"

oc -n argocd patch app "$APP" --type merge \
  -p '{"operation":{"sync":{"syncStrategy":{"apply":{"force":true}}}}}'

echo "OK — instanaKey from Vault/ESO → Application parameters; sync triggered"
oc -n argocd get app "$APP"
oc -n argocd get app "$APP" -o jsonpath='{range .status.conditions[*]}{.type}: {.message}{"\n"}{end}'
