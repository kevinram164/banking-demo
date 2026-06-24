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
        def tlsFlag = cfg.kanikoSkipTlsVerify ? '--skip-tls-verify' : ''
        def tlsArg = tlsFlag ? " \\\n                  ${tlsFlag}" : ''
        def cacheArgs = (cfg.kanikoUseCache != false) ? """
                  --cache=true \\
                  --cache-repo=${cacheRepo}""" : ' \\\n                  --cache=false'

        steps.withCredentials([steps.usernamePassword(
            credentialsId: cfg.harborCredId,
            usernameVariable: 'HARBOR_USER',
            passwordVariable: 'HARBOR_PASS',
        )]) {
            steps.container('kaniko') {
                steps.sh """
                set -e
                mkdir -p /kaniko/.docker
                AUTH=\$(echo -n "\${HARBOR_USER}:\${HARBOR_PASS}" | base64 | tr -d '\\n')
                echo "{\\"auths\\":{\\"${cfg.harborHost}\\":{\\"auth\\":\\"\$AUTH\\"}}}" > /kaniko/.docker/config.json
                /kaniko/executor \\
                  --context=dir://\$(pwd) \\
                  --dockerfile=${meta.dockerfile} \\
                  --destination=${image} \\${cacheArgs}${tlsArg}
                """
            }
        }
        steps.env."IMAGE_TAG_${serviceName.replace('-', '_').toUpperCase()}" = tag
        steps.echo "Pushed ${image}"
    }
}
