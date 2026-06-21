// Jenkinsfile — nhánh dev-k3d (CI in-cluster, không dùng GitHub Actions)
// Job: Multibranch Pipeline, branch filter dev-k3d
// Shared library: banking-demo → phase9-gitops-platform/jenkins-shared-library

@Library('banking-demo') _

bankingDemoPipeline([
  harborHost      : 'harbor-npd.co',
  harborProject   : 'banking-demo',
  gitBranch       : 'dev-k3d',
  gitRepoUrl      : 'https://github.com/YOUR_ORG/banking-demo.git',
  gitopsValuesFile: 'phase9-gitops-platform/gitops/values-images.yaml',
])
