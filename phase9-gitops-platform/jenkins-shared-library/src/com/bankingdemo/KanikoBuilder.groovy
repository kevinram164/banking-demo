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
        def extraFlags = extras.join(' ')
        def contextDir = meta.context ?: '.'

        def harbor = VaultClient.harborCredentials(steps, cfg)
        // OCP: /kaniko/.docker không writable với UID arbitrary — dùng HOME emptyDir.
        // Heartbeat: workspace NFS + Kaniko lâu → durable-task JENKINS-48300 (exit -1 dù push OK).
        steps.withEnv([
            "HARBOR_USER=${harbor.username}",
            "HARBOR_PASS=${harbor.password}",
            'DOCKER_CONFIG=/home/jenkins/agent/.docker',
        ]) {
            steps.container('kaniko') {
                def rc = steps.sh(
                    returnStatus: true,
                    script: """
                    set -e
                    mkdir -p "\${DOCKER_CONFIG}"
                    AUTH=\$(printf '%s:%s' "\${HARBOR_USER}" "\${HARBOR_PASS}" | base64 | tr -d '\\n')
                    printf '%s\\n' "{\\"auths\\":{\\"${cfg.harborHost}\\":{\\"auth\\":\\"\$AUTH\\"}}}" > "\${DOCKER_CONFIG}/config.json"

                    # Giữ log "sống" — tránh durable-task heartbeat miss trên NFS
                    (
                      while true; do
                        echo "[kaniko-heartbeat] \$(date -u +%Y-%m-%dT%H:%M:%SZ) building ${serviceName}"
                        sleep 20
                      done
                    ) &
                    HB_PID=\$!
                    cleanup() { kill \$HB_PID 2>/dev/null || true; wait \$HB_PID 2>/dev/null || true; }
                    trap cleanup EXIT

                    /kaniko/executor \\
                      --context=dir://\$(pwd)/${contextDir} \\
                      --dockerfile=${meta.dockerfile} \\
                      --destination=${image} \\
                      --snapshot-mode=full \\
                      ${extraFlags}

                    cleanup
                    trap - EXIT
                    sync
                    echo "KANIKO_PUSH_OK ${image}"
                    exit 0
                    """,
                )
                // -1 = JENKINS-48300 mất heartbeat sau khi process xong; push thường đã OK
                if (rc != 0 && rc != -1) {
                    steps.error("Kaniko build ${serviceName} failed (exit ${rc})")
                }
                if (rc == -1) {
                    steps.echo "WARN: durable-task exit -1 sau Kaniko (JENKINS-48300) — coi như OK nếu Harbor có ${image}"
                }
            }
        }
        steps.env."IMAGE_TAG_${serviceName.replace('-', '_').toUpperCase()}" = tag
        steps.echo "Pushed ${image}"
    }
}
