package com.bankingdemo

import groovy.json.JsonSlurperClassic

/**
 * Đọc secret KV v2 từ Vault qua Kubernetes auth (SA của agent pod).
 * Không dùng Jenkins Credential Store.
 */
class VaultClient implements Serializable {

    static Map readKv2(def steps, Map cfg, String secretPath) {
        def vaultAddr = (cfg.vaultAddr ?: 'http://vault.vault.svc.cluster.local:8200').replaceAll('/$', '')
        def role = cfg.vaultRole ?: 'jenkins-kaniko'

        // Single-quoted + concat: tránh Groovy GString parse $(...) / $JWT
        def loginScript = '''#!/bin/bash
set -euo pipefail
JWT=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
curl -sS --fail --request POST \\
  --data "{\\"jwt\\": \\"${JWT}\\", \\"role\\": \\"''' + role + '''\\"}" \\
  "''' + vaultAddr + '''/v1/auth/kubernetes/login"
'''
        def loginRaw = steps.sh(script: loginScript, returnStdout: true).trim()
        def login = new JsonSlurperClassic().parseText(loginRaw)
        def clientToken = login.auth.client_token.toString()

        def secretScript = '''#!/bin/bash
set -euo pipefail
curl -sS --fail -H "X-Vault-Token: ''' + clientToken + '''" \\
  "''' + vaultAddr + '''/v1/secret/data/''' + secretPath + '''"
'''
        def secretRaw = steps.sh(script: secretScript, returnStdout: true).trim()
        def secret = new JsonSlurperClassic().parseText(secretRaw)
        return secret.data.data as Map
    }

    static Map harborCredentials(def steps, Map cfg) {
        def path = cfg.vaultHarborPath ?: 'platform/harbor'
        def data = readKv2(steps, cfg, path)
        if (!data.username || !data.password) {
            steps.error("Vault secret/${path} thiếu username hoặc password")
        }
        return [username: data.username.toString(), password: data.password.toString()]
    }

    static Map githubCredentials(def steps, Map cfg) {
        def path = cfg.vaultGithubPath ?: 'platform/github'
        def data = readKv2(steps, cfg, path)
        def user = data.username ?: data.github_username
        def token = data.pat ?: data.github_pat ?: data.password
        if (!user || !token) {
            steps.error("Vault secret/${path} thiếu username/pat")
        }
        return [username: user.toString(), token: token.toString()]
    }
}
