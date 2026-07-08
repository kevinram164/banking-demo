#!groovy
/**
 * Entry pipeline — banking-demo Phase 9 CI
 * @param config harborHost, harborProject, gitBranch, gitopsValuesFile
 */
def call(Map config = [:]) {
    setupParameters()

    def cfg = com.bankingdemo.PipelineConfig.mergeDefaults(config)

    // OCP:
    // - jnlp: emptyDir @ /home/jenkins (UID arbitrary)
    // - kaniko: runAsUser 0 + SCC jenkins-kaniko-root (cần chown rootfs)
    //   scripts/jenkins-kaniko-scc-setup.sh
    podTemplate(
        yamlMergeStrategy: merge(),
        yaml: """
apiVersion: v1
kind: Pod
spec:
  serviceAccountName: jenkins-kaniko
  containers:
    - name: jnlp
      env:
        - name: HOME
          value: /home/jenkins/agent
      workingDir: /home/jenkins/agent
      volumeMounts:
        - name: home-jenkins
          mountPath: /home/jenkins
    - name: kaniko
      image: ${cfg.kanikoImage}
      command: ["/busybox/cat"]
      tty: true
      securityContext:
        runAsUser: 0
        runAsGroup: 0
        runAsNonRoot: false
        allowPrivilegeEscalation: false
      volumeMounts:
        - name: home-jenkins
          mountPath: /home/jenkins
  volumes:
    - name: home-jenkins
      emptyDir: {}
""") {
        node(POD_LABEL) {
            stage('Checkout') {
                checkout scm
                env.GIT_COMMIT = sh(script: 'git rev-parse HEAD', returnStdout: true).trim()
            }

            def targets = com.bankingdemo.ChangeDetector.resolve(this, cfg)
            if (targets.isEmpty()) {
                echo 'Không có service nào được chọn — kết thúc pipeline.'
                currentBuild.result = 'SUCCESS'
                return
            }

            stage('Build & Push') {
                targets.each { svc ->
                    echo "Building ${svc}..."
                    com.bankingdemo.KanikoBuilder.buildAndPush(this, cfg, svc)
                }
            }

            stage('Update GitOps') {
                com.bankingdemo.GitOpsUpdater.bumpImageTags(this, cfg, targets)
            }
        }
    }
}

/** BUILD_TARGET: auto | all | từng service — hiện trên Build with Parameters. */
def setupParameters() {
    properties([
        parameters([
            choice(
                name: 'BUILD_TARGET',
                choices: com.bankingdemo.ChangeDetector.buildTargetChoices(),
                description: '''auto = chỉ service thay đổi trong commit;
all = build mọi service;
hoặc chọn một service cụ thể''',
            ),
        ]),
    ])
}
