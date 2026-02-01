{{/*
  Phase 6 - Deployment Strategies. Helpers cho từng service + slot (blue/green hoặc stable/canary).
*/}}
{{- define "deployment-strategies.labels" -}}
app.kubernetes.io/name: banking-deployment-strategies
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "deployment-strategies.serviceSlotLabels" -}}
app: {{ .name }}
version: {{ .slot }}
{{- end -}}

{{- define "deployment-strategies.serviceSlotSelector" -}}
app: {{ .name }}
version: {{ .slot }}
{{- end -}}

{{/* fullname cho Deployment/Service theo slot: auth-service-blue, auth-service-green */}}
{{- define "deployment-strategies.fullname" -}}
{{- printf "%s-%s" .name .slot -}}
{{- end -}}
