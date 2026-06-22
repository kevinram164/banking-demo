#!groovy
/**
 * Entry pipeline — banking-demo Phase 9 CI
 * @param config harborHost, harborProject, gitBranch, gitopsValuesFile
 */
def call(Map config = [:]) {
    def cfg = com.bankingdemo.PipelineConfig.mergeDefaults(config)

    podTemplate(yaml: """
apiVersion: v1
kind: Pod
spec:
  serviceAccountName: jenkins-kaniko
  containers:
    - name: kaniko
      image: ${cfg.kanikoImage}
      command: ["/busybox/cat"]
      tty: true
""") {
        node(POD_LABEL) {
            stage('Checkout') {
                checkout scm
            }

            def changed = com.bankingdemo.ChangeDetector.detect(this, cfg)
            if (changed.isEmpty()) {
                echo 'No Phase 8 service changes — skip build.'
                return
            }

            stage('Build & Push') {
                changed.each { svc ->
                    com.bankingdemo.KanikoBuilder.buildAndPush(this, cfg, svc)
                }
            }

            stage('Update GitOps') {
                com.bankingdemo.GitOpsUpdater.bumpImageTags(this, cfg, changed)
            }
        }
    }
}
