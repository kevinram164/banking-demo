# SCC — chạy sau helm install (ServiceAccount từ chart csi-driver-nfs v4.11.0)
# oc adm policy add-scc-to-user privileged system:serviceaccount:csi-driver-nfs:csi-nfs-node-sa
# oc adm policy add-scc-to-user privileged system:serviceaccount:csi-driver-nfs:csi-nfs-controller-sa
