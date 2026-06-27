// Jenkinsfile — nhánh dev-ocp (OpenShift, CI in-cluster)
// Job: Multibranch Pipeline, branch filter dev-ocp
// Shared library: banking-demo → phase9-gitops-platform/jenkins-shared-library
//
// Build with Parameters → BUILD_TARGET:
//   auto  — chỉ service có diff (mặc định)
//   all   — build mọi service
//   <tên> — build một service (vd account-service)
//
// Harbor host: chỉnh theo Route OCP — xem environments/dev-ocp/gitops-env.yaml

@Library('banking-demo') _

bankingDemoPipeline([
  harborHost           : 'harbor-banking.apps.ocp01.npd.co',
  harborProject        : 'banking-demo',
  gitBranch            : 'dev-ocp',
  gitRepoUrl           : 'https://github.com/kevinram164/banking-demo.git',
  gitopsValuesFile     : 'phase9-gitops-platform/gitops/values-images.yaml',
  kanikoSkipTlsVerify  : true,
  kanikoUseCache       : false,
])
