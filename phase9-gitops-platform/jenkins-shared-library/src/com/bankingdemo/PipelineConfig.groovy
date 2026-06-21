package com.bankingdemo

class PipelineConfig implements Serializable {

    static final Map SERVICES = [
        'api-producer': [
            dockerfile: 'phase8-application-v3/producer/Dockerfile',
            context   : '.',
            helmKey   : 'api-producer',
        ],
        'auth-service': [
            dockerfile: 'phase8-application-v3/services/auth-service/Dockerfile',
            context   : '.',
            helmKey   : 'auth-service',
        ],
        'account-service': [
            dockerfile: 'phase8-application-v3/services/account-service/Dockerfile',
            context   : '.',
            helmKey   : 'account-service',
        ],
        'transfer-service': [
            dockerfile: 'phase8-application-v3/services/transfer-service/Dockerfile',
            context   : '.',
            helmKey   : 'transfer-service',
        ],
        'notification-service': [
            dockerfile: 'phase8-application-v3/services/notification-service/Dockerfile',
            context   : '.',
            helmKey   : 'notification-service',
        ],
    ]

    static Map mergeDefaults(Map user) {
        def defaults = [
            harborHost       : 'harbor.example.com',
            harborProject    : 'banking-demo',
            gitBranch        : 'main',
            gitRepoUrl       : 'https://github.com/kevinram164/banking-demo.git',
            gitopsValuesFile : 'phase9-gitops-platform/gitops/values-images.yaml',
            kanikoImage      : 'gcr.io/kaniko-project/executor:v1.23.2',
            harborCredId     : 'harbor-ci-push',
            gitopsCredId     : 'github-gitops-push',
            watchPathPrefix  : 'phase8-application-v3/',
        ]
        return defaults + user
    }
}
