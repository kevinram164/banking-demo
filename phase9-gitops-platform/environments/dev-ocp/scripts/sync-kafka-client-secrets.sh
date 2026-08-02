#!/usr/bin/env bash
# Copy Strimzi SCRAM user + cluster CA vào ns npd-banking (chạy trên bastion sau KafkaUser Ready).
set -euo pipefail

SRC_NS="${SRC_NS:-kafka}"
DST_NS="${DST_NS:-npd-banking}"
USER_SECRET="${USER_SECRET:-npd-banking}"
CA_SECRET="${CA_SECRET:-npd-kafka-cluster-ca-cert}"

oc -n "$SRC_NS" get secret "$USER_SECRET" >/dev/null
oc -n "$SRC_NS" get secret "$CA_SECRET" >/dev/null

oc -n "$SRC_NS" get secret "$USER_SECRET" -o json \
  | jq --arg ns "$DST_NS" \
    'del(.metadata.uid,.metadata.resourceVersion,.metadata.creationTimestamp,.metadata.ownerReferences,.metadata.annotations,.metadata.managedFields)
     | .metadata.namespace=$ns
     | .metadata.name="npd-banking-kafka-user"
     | .type="Opaque"' \
  | oc apply -f -

oc -n "$SRC_NS" get secret "$CA_SECRET" -o json \
  | jq --arg ns "$DST_NS" \
    'del(.metadata.uid,.metadata.resourceVersion,.metadata.creationTimestamp,.metadata.ownerReferences,.metadata.annotations,.metadata.managedFields)
     | .metadata.namespace=$ns
     | .metadata.name="npd-banking-kafka-cluster-ca"
     | .type="Opaque"' \
  | oc apply -f -

echo "OK: $DST_NS/npd-banking-kafka-user + $DST_NS/npd-banking-kafka-cluster-ca"
oc -n "$DST_NS" get secret npd-banking-kafka-user npd-banking-kafka-cluster-ca
