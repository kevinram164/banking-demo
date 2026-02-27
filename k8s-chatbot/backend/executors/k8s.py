"""Execute Kubernetes API operations."""
from datetime import datetime
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from config import K8S_IN_CLUSTER, K8S_NAMESPACE
from agents.parser import CommandIntent


def _get_client():
    if K8S_IN_CLUSTER:
        config.load_incluster_config()
    else:
        config.load_kube_config()
    return client.CoreV1Api(), client.AppsV1Api()


def k8s_execute(intent: CommandIntent) -> str:
    core, apps = _get_client()
    ns = intent.namespace or K8S_NAMESPACE

    try:
        if intent.action == "get_pods":
            ret = core.list_namespaced_pod(namespace=ns, watch=False)
            lines = [f"{p.metadata.name}\t{p.status.phase}\t{p.status.container_statuses[0].ready if p.status.container_statuses else 'N/A'}" for p in ret.items]
            header = "NAME\tSTATUS\tREADY\n"
            return header + "\n".join(lines) if lines else f"No pods in namespace {ns}"

        if intent.action == "get_deployments":
            ret = apps.list_namespaced_deployment(namespace=ns, watch=False)
            lines = []
            for d in ret.items:
                ready = d.status.ready_replicas or 0
                total = d.spec.replicas or 0
                msg = d.status.conditions[-1].message if d.status.conditions else "-"
                lines.append(f"{d.metadata.name}\t{ready}/{total}\t{msg}")
            header = "NAME\tREADY\tMESSAGE\n"
            return header + "\n".join(lines) if lines else f"No deployments in namespace {ns}"

        if intent.action == "get_logs":
            # Try kubectl logs when we have pod name - search in ns or all
            pod_name = intent.resource_name
            if not pod_name:
                return "Please specify pod name for logs"
            namespaces = [ns] if ns else ["banking", "monitoring", "default"]
            # apiserver / kube-apiserver thường ở kube-system
            if "apiserver" in pod_name.lower() and "kube-system" not in namespaces:
                namespaces = ["kube-system"] + namespaces
            # Tìm pod: apiserver → match kube-apiserver-*
            search_terms = [pod_name]
            if pod_name.lower() == "apiserver":
                search_terms = ["kube-apiserver", "apiserver"]
            for search_ns in namespaces:
                try:
                    pods = core.list_namespaced_pod(namespace=search_ns, watch=False)
                    matched = [p for p in pods.items if any(t in p.metadata.name.lower() for t in search_terms)]
                    if matched:
                        p = matched[0]
                        tail = intent.log_tail
                        log = core.read_namespaced_pod_log(
                            name=p.metadata.name,
                            namespace=search_ns,
                            tail_lines=tail,
                        )
                        if intent.log_filter:
                            lines = [l for l in log.split("\n") if intent.log_filter.lower() in l.lower()]
                            log = "\n".join(lines) if lines else f"No lines matching '{intent.log_filter}'"
                        return f"[{p.metadata.name} in {search_ns}]\n{log}"
                except ApiException:
                    continue
            return f"Pod matching '{pod_name}' not found in {namespaces}"

        if intent.action == "rollout_restart":
            if intent.resource_name:
                name = intent.resource_name
            else:
                # Restart all deployments in namespace
                ret = apps.list_namespaced_deployment(namespace=ns, watch=False)
                results = []
                for d in ret.items:
                    try:
                        ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                        apps.patch_namespaced_deployment(
                            name=d.metadata.name,
                            namespace=ns,
                            body={"spec": {"template": {"metadata": {"annotations": {"kubectl.kubernetes.io/restartedAt": ts}}}}},
                        )
                        results.append(f"Restarted {d.metadata.name}")
                    except ApiException as e:
                        results.append(f"Failed {d.metadata.name}: {e.reason}")
                return "\n".join(results) if results else f"No deployments in {ns}"
            try:
                ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                apps.patch_namespaced_deployment(
                    name=name,
                    namespace=ns,
                    body={"spec": {"template": {"metadata": {"annotations": {"kubectl.kubernetes.io/restartedAt": ts}}}}},
                )
                return f"Rollout restart triggered for deployment {name} in {ns}"
            except ApiException as e:
                return f"Error: {e.reason} - {e.body}"

        return "Unknown K8s action"
    except ApiException as e:
        return f"Kubernetes API error: {e.reason}\n{e.body}"
