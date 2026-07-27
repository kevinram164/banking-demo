// Jenkinsfile — nhánh dev-ocp (OpenShift, CI in-cluster)
// Shared library trung tâm: https://github.com/kevinram164/jenkins-shared-library
//
// BUILD_TARGET: auto | all | <service>

@Library('platform@main') _

platformPipeline([
  project              : 'banking-demo',
  harborHost           : 'harbor-platform.apps.ocp01.npd.co',
  harborProject        : 'banking-demo',
  gitBranch            : 'dev-ocp',
  gitRepoUrl           : 'https://github.com/kevinram164/banking-demo.git',
  gitopsValuesFile     : 'phase9-gitops-platform/gitops/values-images.yaml',
  kanikoSkipTlsVerify  : true,
  kanikoUseCache       : false,
  vaultAddr            : 'http://vault.vault.svc.cluster.local:8200',
  vaultRole            : 'jenkins-kaniko',
  vaultHarborPath      : 'platform/harbor',
  vaultGithubPath      : 'platform/github',
])
