{{/*
Chart name and version, used in the "helm.sh/chart" label.
*/}}
{{- define "cluster-agent.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Fully-qualified resource name.
*/}}
{{- define "cluster-agent.fullname" -}}
{{- printf "%s-cluster-agent" .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels applied to every resource.
*/}}
{{- define "cluster-agent.labels" -}}
helm.sh/chart: {{ include "cluster-agent.chart" . }}
app.kubernetes.io/name: cluster-agent
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}

{{/*
Selector labels — deliberately a subset of the full labels (no chart
version/managed-by), matching the kubex-agent chart's convention so a
`helm upgrade` across chart versions never has to touch immutable selectors.
*/}}
{{- define "cluster-agent.selectorLabels" -}}
app.kubernetes.io/name: cluster-agent
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
