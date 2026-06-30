#!/usr/bin/env bash
# Xóa Vault Agent Injector còn sót (ImagePullBackOff vault-k8s:1.4.2 trên OCP).
# Phase 9 dùng ESO — không cần injector. Chạy trước khi sync platform-vault.
set -euo pipefail

NS="${1:-vault}"

echo "==> Remove vault-agent-injector in namespace: ${NS}"
oc delete deployment vault-agent-injector -n "${NS}" --ignore-not-found
oc delete service vault-agent-injector-svc -n "${NS}" --ignore-not-found
oc delete mutatingwebhookconfiguration vault-agent-injector-cfg --ignore-not-found
oc delete mutatingwebhookconfiguration vault-agent-injector-cfg-secondary --ignore-not-found 2>/dev/null || true

echo "==> Remaining pods in ${NS}:"
oc get pods -n "${NS}"
