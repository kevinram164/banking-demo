package com.bankingdemo

class PipelineConfig implements Serializable {

    static final Map SERVICES = [
        'api-producer': [
            dockerfile  : 'phase8-application-v3/producer/Dockerfile',
            context     : '.',
            helmKey     : 'api-producer',
            snapshotMode: 'full',   // pip/venv — tránh miss layer
        ],
        'auth-service': [
            dockerfile  : 'phase8-application-v3/services/auth-service/Dockerfile',
            context     : '.',
            helmKey     : 'auth-service',
            snapshotMode: 'full',
        ],
        'account-service': [
            dockerfile  : 'phase8-application-v3/services/account-service/Dockerfile',
            context     : '.',
            helmKey     : 'account-service',
            snapshotMode: 'full',
        ],
        'transfer-service': [
            dockerfile  : 'phase8-application-v3/services/transfer-service/Dockerfile',
            context     : '.',
            helmKey     : 'transfer-service',
            snapshotMode: 'full',
        ],
        'notification-service': [
            dockerfile  : 'phase8-application-v3/services/notification-service/Dockerfile',
            context     : '.',
            helmKey     : 'notification-service',
            snapshotMode: 'full',
        ],
        'shop-bridge': [
            dockerfile  : 'phase8-application-v3/services/shop-bridge/Dockerfile',
            context     : '.',
            helmKey     : 'shop-bridge',
            snapshotMode: 'full',
        ],
        'frontend': [
            dockerfile  : 'Dockerfile',
            context     : 'frontend',
            helmKey     : 'frontend',
            watchPath   : 'frontend',
            // Không dùng full: npm tạo hàng chục nghìn file → snapshot cực chậm + stage treo
            snapshotMode: 'time',
        ],
    ]

    static Map mergeDefaults(Map user) {
        def defaults = [
            harborHost         : 'harbor.example.com',
            harborProject      : 'banking-demo',
            gitBranch          : 'main',
            gitRepoUrl         : 'https://github.com/kevinram164/banking-demo.git',
            gitopsValuesFile   : 'phase9-gitops-platform/gitops/values-images.yaml',
            kanikoImage        : 'gcr.io/kaniko-project/executor:v1.23.2-debug',
            kanikoSkipTlsVerify: false,
            kanikoUseCache     : false,
            vaultAddr          : 'http://vault.vault.svc.cluster.local:8200',
            vaultRole          : 'jenkins-kaniko',
            vaultHarborPath    : 'platform/harbor',
            vaultGithubPath    : 'platform/github',
        ]
        return defaults + user
    }
}
