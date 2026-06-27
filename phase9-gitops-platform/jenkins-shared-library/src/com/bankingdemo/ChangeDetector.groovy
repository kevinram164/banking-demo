package com.bankingdemo

class ChangeDetector implements Serializable {

    /** Lựa chọn trên UI Jenkins (Build with Parameters). */
    static List<String> buildTargetChoices() {
        def services = PipelineConfig.SERVICES.keySet().sort() as List
        return ['auto', 'all'] + services
    }

    /**
     * Xác định danh sách service cần build.
     * BUILD_TARGET: auto | all | tên service
     */
    static List<String> resolve(def steps, Map cfg) {
        def all = PipelineConfig.SERVICES.keySet().sort() as List

        if (steps.env.FORCE_BUILD_ALL == 'true') {
            steps.echo 'FORCE_BUILD_ALL=true — build all services'
            return all
        }

        def target = steps.params?.BUILD_TARGET ?: cfg.buildTarget ?: 'auto'
        steps.echo "BUILD_TARGET=${target}"

        if (target == 'all') {
            return all
        }
        if (target != 'auto') {
            if (!PipelineConfig.SERVICES.containsKey(target)) {
                steps.error("Unknown BUILD_TARGET: ${target}")
            }
            return [target]
        }

        return detectChanged(steps, cfg, all)
    }

    /** auto — chỉ build service có file thay đổi trong commit. */
    private static List<String> detectChanged(def steps, Map cfg, List<String> all) {
        def changed = [] as Set
        try {
            def diff = steps.sh(
                script: "git diff --name-only HEAD~1 HEAD 2>/dev/null || git diff --name-only origin/${cfg.gitBranch}...HEAD",
                returnStdout: true,
            ).trim()
            if (!diff) {
                steps.echo 'auto: không có diff — bỏ qua build. Chọn BUILD_TARGET=all hoặc tên service nếu cần build thủ công.'
                return []
            }
            diff.split('\n').each { path ->
                if (path.startsWith('phase8-application-v3/common/')) {
                    changed.addAll(all)
                } else {
                    PipelineConfig.SERVICES.each { name, meta ->
                        def serviceDir = meta.dockerfile.replace('/Dockerfile', '')
                        if (path.startsWith("${serviceDir}/") || path == meta.dockerfile) {
                            changed << name
                        }
                    }
                }
            }
        } catch (ignored) {
            steps.echo 'auto: change detection failed — bỏ qua build (chọn all hoặc service cụ thể).'
            return []
        }
        if (changed.isEmpty()) {
            steps.echo 'auto: diff không chạm Phase 8 services — bỏ qua build.'
        } else {
            steps.echo "auto: build ${changed.sort().join(', ')}"
        }
        return changed.sort() as List
    }
}
