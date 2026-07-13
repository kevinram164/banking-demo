package com.bankingdemo

class KanikoBuilder implements Serializable {

    static void buildAndPush(def steps, Map cfg, String serviceName) {
        def meta = PipelineConfig.SERVICES[serviceName]
        if (!meta) {
            steps.error("Unknown service: ${serviceName}")
        }
        def tag = GitRef.imageTag(steps)
        def image = "${cfg.harborHost}/${cfg.harborProject}/${serviceName}:${tag}"
        def cacheRepo = "${cfg.harborHost}/${cfg.harborProject}/cache/${serviceName}"

        def extras = []
        if (cfg.kanikoUseCache != false) {
            extras << '--cache=true'
            extras << "--cache-repo=${cacheRepo}"
        } else {
            extras << '--cache=false'
        }
        if (cfg.kanikoSkipTlsVerify) {
            extras << '--skip-tls-verify'
        }
        // Python: full (tránh miss pip). Frontend: time (npm quá nhiều file → full rất chậm).
        def snap = meta.snapshotMode ?: 'time'
        extras << "--snapshot-mode=${snap}"
        // Giữ busybox/kaniko/home khỏi bị layer image đè (build sau cùng pod).
        extras << '--ignore-path=/busybox'
        extras << '--ignore-path=/kaniko'
        extras << '--ignore-path=/home/jenkins'
        def extraFlags = extras.join(' ')
        def contextDir = meta.context ?: '.'

        def harbor = VaultClient.harborCredentials(steps, cfg)
        steps.withEnv([
            "HARBOR_USER=${harbor.username}",
            "HARBOR_PASS=${harbor.password}",
            'DOCKER_CONFIG=/home/jenkins/agent/.docker',
        ]) {
            // Shell trên emptyDir — sống sau khi Kaniko unpack đè /busybox.
            steps.container(name: 'kaniko', shell: '/home/jenkins/agent/bin/sh') {
                def rc = steps.sh(
                    returnStatus: true,
                    script: """
                    set -e
                    mkdir -p "\${DOCKER_CONFIG}"
                    AUTH=\$(printf '%s:%s' "\${HARBOR_USER}" "\${HARBOR_PASS}" | base64 | tr -d '\\n')
                    printf '%s\\n' "{\\"auths\\":{\\"${cfg.harborHost}\\":{\\"auth\\":\\"\$AUTH\\"}}}" > "\${DOCKER_CONFIG}/config.json"
                    /kaniko/executor \\
                      --context=dir://\$(pwd)/${contextDir} \\
                      --dockerfile=${meta.dockerfile} \\
                      --destination=${image} \\
                      ${extraFlags}
                    echo "KANIKO_PUSH_OK ${image}"
                    """,
                )
                if (rc != 0 && rc != -1) {
                    steps.error("Kaniko build ${serviceName} failed (exit ${rc})")
                }
                if (rc == -1) {
                    steps.echo "WARN: durable-task exit -1 (JENKINS-48300) — kiểm tra Harbor có ${image}"
                }
            }
        }
        steps.env."IMAGE_TAG_${serviceName.replace('-', '_').toUpperCase()}" = tag
        steps.echo "Pushed ${image}"
    }
}
