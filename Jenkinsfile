// Jenkinsfile — nhánh dev-k3d (CI in-cluster, không dùng GitHub Actions)
// Job: Multibranch Pipeline, branch filter dev-k3d
// Shared library: banking-demo → phase9-gitops-platform/jenkins-shared-library
//
// Build with Parameters → BUILD_TARGET:
//   auto  — chỉ service có diff (mặc định)
//   all   — build mọi service
//   <tên> — build một service (vd account-service)

@Library('banking-demo') _

bankingDemoPipeline([
  harborHost           : 'harbor-npd.co',
  harborProject        : 'banking-demo',
  gitBranch            : 'dev-k3d',
  gitRepoUrl           : 'https://github.com/kevinram164/banking-demo.git',
  gitopsValuesFile     : 'phase9-gitops-platform/gitops/values-images.yaml',
  kanikoSkipTlsVerify  : true,   // Harbor lab: cert self-signed / nginx terminate SSL
  kanikoUseCache       : false,  // lab: tránh cache layer lỗi (uvicorn not found)
])
