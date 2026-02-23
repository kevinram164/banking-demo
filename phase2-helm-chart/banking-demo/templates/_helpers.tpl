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
