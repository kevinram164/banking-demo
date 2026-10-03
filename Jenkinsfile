// Jenkinsfile — nhánh dev-k8s (kubeadm K8s, CI in-cluster trên Jenkins của cloud-native-platform)
// Shared library trung tâm: https://github.com/kevinram164/jenkins-shared-library
// CD: Jenkins bump tag trong deploy/dev-k8s/values/values-images.yaml (cùng repo) → ArgoCD sync.
//
// BUILD_TARGET: auto | all | <service>

@Library('platform@main') _

platformPipeline([
  project              : 'banking-demo',
  harborHost           : 'harbor-npd.co',
  harborProject        : 'banking-demo',
  gitBranch            : 'dev-k8s',
  gitRepoUrl           : 'https://github.com/kevinram164/banking-demo.git',
  gitopsValuesFile     : 'deploy/dev-k8s/values/values-images.yaml',
  kanikoSkipTlsVerify  : true,
  kanikoUseCache       : false,
  vaultAddr            : 'http://vault.vault.svc.cluster.local:8200',
  vaultRole            : 'jenkins-kaniko',
  vaultHarborPath      : 'platform/harbor',
  vaultGithubPath      : 'platform/github',
])
