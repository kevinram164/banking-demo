{{/*
  Helper: tên đầy đủ dùng cho Deployment/Service (có thể override bằng release name)
*/}}
{{- define "quickstart-app.fullname" -}}
{{- default .Chart.Name .Values.name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
