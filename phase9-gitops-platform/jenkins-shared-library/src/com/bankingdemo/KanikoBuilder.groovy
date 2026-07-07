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

        def harbor = VaultClient.harborCredentials(steps, cfg)
        steps.withEnv([
            "HARBOR_USER=${harbor.username}",
            "HARBOR_PASS=${harbor.password}",
        ]) {
            steps.container('kaniko') {
                steps.sh """
                set -e
                mkdir -p /kaniko/.docker
                AUTH=\$(echo -n "\${HARBOR_USER}:\${HARBOR_PASS}" | base64 | tr -d '\\n')
                echo "{\\"auths\\":{\\"${cfg.harborHost}\\":{\\"auth\\":\\"\$AUTH\\"}}}" > /kaniko/.docker/config.json
                /kaniko/executor \\
                  --context=dir://\$(pwd) \\
                  --dockerfile=${meta.dockerfile} \\
                  --destination=${image} \\
                  ${extraFlags}
                """
            }
        }
        steps.env."IMAGE_TAG_${serviceName.replace('-', '_').toUpperCase()}" = tag
        steps.echo "Pushed ${image}"
    }
}
