{{/*
  Banking Demo - Helm chart helpers (Phase 2). Templates dùng chung; values theo từng service trong charts/<name>/values.yaml
*/}}
{{- define "banking-demo.namespace" -}}
{{- .Release.Namespace -}}
{{- end -}}

{{- define "banking-demo.labels" -}}
app.kubernetes.io/name: banking-demo
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "banking-demo.selectorLabels" -}}
app.kubernetes.io/name: banking-demo
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "banking-demo.corsOrigins" -}}
{{- default "http://localhost:3000" .Values.global.corsOrigins -}}
{{- end -}}

{{- define "banking-demo.secretName" -}}
{{- default "banking-db-secret" .Values.global.secretName -}}
{{- end -}}

{{/* --- Component helpers (values from .Values.<component>) --- */}}
{{- define "banking-demo.postgres.fullname" -}}{{- .Values.postgres.fullnameOverride | default "postgres" -}}{{- end -}}
{{- define "banking-demo.postgres.labels" -}}
app.kubernetes.io/name: {{ include "banking-demo.postgres.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: postgres
{{- end -}}
{{- define "banking-demo.postgres.selectorLabels" -}}
app.kubernetes.io/name: {{ include "banking-demo.postgres.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "banking-demo.redis.fullname" -}}{{- .Values.redis.fullnameOverride | default "redis" -}}{{- end -}}
{{- define "banking-demo.redis.labels" -}}
app.kubernetes.io/name: {{ include "banking-demo.redis.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: redis
{{- end -}}
{{- define "banking-demo.redis.selectorLabels" -}}
app.kubernetes.io/name: {{ include "banking-demo.redis.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "banking-demo.kong.fullname" -}}{{- .Values.kong.fullnameOverride | default "kong" -}}{{- end -}}
{{- define "banking-demo.kong.configMapName" -}}{{- .Values.kong.configMapName | default "kong-config" -}}{{- end -}}
{{- define "banking-demo.kong.labels" -}}
app.kubernetes.io/name: {{ include "banking-demo.kong.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: kong
{{- end -}}
{{- define "banking-demo.kong.selectorLabels" -}}
app.kubernetes.io/name: {{ include "banking-demo.kong.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "banking-demo.auth-service.fullname" -}}{{- (index .Values "auth-service").fullnameOverride | default "auth-service" -}}{{- end -}}
{{- define "banking-demo.auth-service.labels" -}}
app.kubernetes.io/name: {{ include "banking-demo.auth-service.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: auth-service
{{- end -}}
{{- define "banking-demo.auth-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "banking-demo.auth-service.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "banking-demo.account-service.fullname" -}}{{- (index .Values "account-service").fullnameOverride | default "account-service" -}}{{- end -}}
{{- define "banking-demo.account-service.labels" -}}
app.kubernetes.io/name: {{ include "banking-demo.account-service.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: account-service
{{- end -}}
{{- define "banking-demo.account-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "banking-demo.account-service.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "banking-demo.transfer-service.fullname" -}}{{- (index .Values "transfer-service").fullnameOverride | default "transfer-service" -}}{{- end -}}
{{- define "banking-demo.transfer-service.labels" -}}
app.kubernetes.io/name: {{ include "banking-demo.transfer-service.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: transfer-service
{{- end -}}
{{- define "banking-demo.transfer-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "banking-demo.transfer-service.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "banking-demo.shop-bridge.fullname" -}}{{- (index .Values "shop-bridge" | default dict).fullnameOverride | default "shop-bridge" -}}{{- end -}}
{{- define "banking-demo.shop-bridge.labels" -}}
app.kubernetes.io/name: {{ include "banking-demo.shop-bridge.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: shop-bridge
{{- end -}}
{{- define "banking-demo.shop-bridge.selectorLabels" -}}
app.kubernetes.io/name: {{ include "banking-demo.shop-bridge.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "banking-demo.notification-service.fullname" -}}{{- (index .Values "notification-service").fullnameOverride | default "notification-service" -}}{{- end -}}
{{- define "banking-demo.notification-service.labels" -}}
app.kubernetes.io/name: {{ include "banking-demo.notification-service.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: notification-service
{{- end -}}
{{- define "banking-demo.notification-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "banking-demo.notification-service.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "banking-demo.frontend.fullname" -}}{{- .Values.frontend.fullnameOverride | default "frontend" -}}{{- end -}}

{{- define "banking-demo.api-producer.fullname" -}}{{- (index .Values "api-producer").fullnameOverride | default "api-producer" -}}{{- end -}}
{{- define "banking-demo.api-producer.labels" -}}
app.kubernetes.io/name: {{ include "banking-demo.api-producer.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: api-producer
{{- end -}}
{{- define "banking-demo.api-producer.selectorLabels" -}}
app.kubernetes.io/name: {{ include "banking-demo.api-producer.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "banking-demo.rabbitmq.fullname" -}}{{- (index .Values "rabbitmq").fullnameOverride | default "rabbitmq" -}}{{- end -}}
{{- define "banking-demo.rabbitmq.labels" -}}
app.kubernetes.io/name: {{ include "banking-demo.rabbitmq.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: rabbitmq
{{- end -}}
{{- define "banking-demo.rabbitmq.selectorLabels" -}}
app.kubernetes.io/name: {{ include "banking-demo.rabbitmq.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
{{- define "banking-demo.frontend.labels" -}}
app.kubernetes.io/name: {{ include "banking-demo.frontend.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: frontend
{{- end -}}
{{- define "banking-demo.frontend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "banking-demo.frontend.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "banking-demo.vault.enabled" -}}
{{- $g := .Values.global | default dict -}}
{{- $v := $g.vault | default dict -}}
{{- if $v.enabled }}true{{ end -}}
{{- end -}}

{{/* Vault template syntax is wrapped in backticks so Helm leaves it for the agent. */}}
{{- define "banking-demo.vault.podAnnotations" -}}
{{- $v := .Values.global.vault -}}
vault.hashicorp.com/agent-inject: "true"
vault.hashicorp.com/agent-init-first: "true"
vault.hashicorp.com/agent-pre-populate-only: "true"
vault.hashicorp.com/role: {{ $v.role | quote }}
vault.hashicorp.com/agent-inject-secret-env: {{ $v.dbPath | quote }}
vault.hashicorp.com/agent-inject-template-env: |
  {{`{{ with secret "`}}{{ $v.dbPath }}{{`" }}`}}
  export DATABASE_URL='{{`{{ .Data.data.DATABASE_URL }}`}}'
  export REDIS_URL='{{`{{ .Data.data.REDIS_URL }}`}}'
  {{`{{ end }}`}}
  {{`{{ with secret "`}}{{ $v.rabbitmqPath }}{{`" }}`}}
  export RABBITMQ_URL='{{`{{ .Data.data.RABBITMQ_URL }}`}}'
  {{`{{ end }}`}}
{{- end -}}

{{/* Usage: include "banking-demo.vault.command" (dict "port" $svc.service.port) */}}
{{- define "banking-demo.vault.command" -}}
command: ["/bin/sh", "-c"]
args:
  - . /vault/secrets/env && exec /app/venv/bin/uvicorn main:app --host 0.0.0.0 --port {{ .port }} --no-access-log
{{- end -}}
