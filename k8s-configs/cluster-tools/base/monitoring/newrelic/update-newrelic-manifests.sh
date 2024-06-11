#!/bin/bash
set -e

USAGE="./update-newrelic-manifests.sh /Users/ysinha/p1as-observability/deploy/p1as-newrelic/nr-manifests.yaml"
REQ_PATH="/Users/ysinha/ping-cloud-base/k8s-configs/cluster-tools/base/monitoring/newrelic"
NR_MANIFESTS_YAML="${1}"

if [[ ! "$(pwd)" = "${REQ_PATH}" ]]; then
    echo "Script run source sanity check failed. Please only run this script in ${REQ_PATH}"
    exit 1
fi

if [[ $# != 1 ]]; then
    echo "Usage: ${USAGE}"
    exit 1
fi

if [[ ! -f "${NR_MANIFESTS_YAML}" ]]; then
    echo "File ${NR_MANIFESTS_YAML} does not exist."
    exit 1
fi

# Function to extract and update a specific section
update_section() {
    local resource_kind="$1"
    local output_file="$2"

    echo "Updating ${resource_kind}..."
    yq eval-all 'select(.kind == "'${resource_kind}'")' "${NR_MANIFESTS_YAML}" > "${output_file}"
}

# Change to the target directory
cd "${REQ_PATH}"

# Update each YAML file with the corresponding section from nr-manifests.yaml
update_section "ClusterRole" "clusterrole.yaml"
update_section "ClusterRoleBinding" "clusterrolebinding.yaml"
update_section "ConfigMap" "configmap.yaml"
update_section "DaemonSet" "daemonset.yaml"
update_section "Deployment" "deployment.yaml"
update_section "Job" "job.yaml"
update_section "Namespace" "namespace.yaml"
update_section "Role" "role.yaml"
update_section "RoleBinding" "rolebinding.yaml"
update_section "Secret" "secret.yaml"
update_section "Service" "service.yaml"
update_section "ServiceAccount" "serviceaccount.yaml"
update_section "StatefulSet" "statefulset.yaml"
update_section "MutatingWebhookConfiguration" "mutationwebhookconfiguration.yaml"

# Handle kustomization.yaml and newrelic-aio.yaml specifically if they have custom logic
echo "Updating kustomization.yaml..."
# Assuming this file is a simple replacement. If it has custom logic, handle accordingly.
cp "${NR_MANIFESTS_YAML}" "kustomization.yaml" # Adjust this line if you have a specific section to extract.

echo "Updating newrelic-aio.yaml..."
# Assuming this file is a simple replacement. If it has custom logic, handle accordingly.
cp "${NR_MANIFESTS_YAML}" "newrelic-aio.yaml" # Adjust this line if you have a specific section to extract.

echo "Update complete, check your 'git diff' to see what changed"

