#!/bin/bash

# Set ping-cloud PING_CLOUD_NAMESPACE
# Note: The regular expression \bping-cloud\S* matches any string that starts with "ping-cloud" (\bping-cloud) and has zero or more non-space characters after it (\S*).
# e.g.
# A CDE with ping-cloud namespace will set the variable NAMESPACE as 'ping-cloud'
# A CDE with ping-cloud-username namespace will set the variable NAMESPACE as 'ping-cloud-username'
export PING_CLOUD_NAMESPACE=$(kubectl get namespaces -o jsonpath='{.items[*].metadata.name}{"\n"}' | grep -o -E "\bping-cloud\S*")

# Get desired PingDirectory pod name
BACKUP_RESTORE_POD=$(kubectl get configmap pingdirectory-environment-variables -o jsonpath='{.data.BACKUP_RESTORE_POD}' -n "${PING_CLOUD_NAMESPACE}")
K8S_STATEFUL_SET_NAME=$(kubectl get configmap pingdirectory-environment-variables -o jsonpath='{.data.K8S_STATEFUL_SET_NAME}' -n "${PING_CLOUD_NAMESPACE}")
test -z "${BACKUP_RESTORE_POD}" && export PINGDIRECTORY_POD_NAME="${K8S_STATEFUL_SET_NAME}-0" || export PINGDIRECTORY_POD_NAME="${BACKUP_RESTORE_POD}"

# Get desired PingDirectory PVC size
export PINGDIRECTORY_PVC_SIZE=$(kubectl get pvc "out-dir-${PINGDIRECTORY_POD_NAME}" -o jsonpath='{.spec.resources.requests.storage}' -n "${PING_CLOUD_NAMESPACE}")

parent_directory="$(dirname "$(realpath "$0")")"
cat "${parent_directory}/restore-pvc.yaml" | envsubst | kubectl apply -f -
cat "${parent_directory}/restore-cm.yaml"  | kubectl apply -f -
cat "${parent_directory}/restore-job.yaml" | envsubst | kubectl apply -f -