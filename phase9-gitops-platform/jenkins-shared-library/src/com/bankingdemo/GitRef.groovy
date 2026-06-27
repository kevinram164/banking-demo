package com.bankingdemo

class GitRef implements Serializable {

    /** Tag image = 7 ký tự SHA; fallback git trong workspace (pod agent đôi khi thiếu GIT_COMMIT). */
    static String imageTag(def steps) {
        def fromEnv = steps.env.GIT_COMMIT?.take(7)
        if (fromEnv) {
            return fromEnv
        }
        return steps.sh(script: 'git rev-parse --short=7 HEAD', returnStdout: true).trim()
    }
}
