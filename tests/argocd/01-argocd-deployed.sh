#!/bin/bash

CI_SCRIPTS_DIR="${SHARED_CI_SCRIPTS_DIR:-/ci-scripts}"
. "${CI_SCRIPTS_DIR}"/common.sh "${1}"

if skipTest "${0}"; then
  log "Skipping test ${0}"
  exit 0
fi

checkWorkloadStatus() {
  workload=$1
  # get workload name, available replicas, and desired replicas
  workloads=$(kubectl get "$workload" -n argocd -o jsonpath='{range .items[*]}{.metadata.name} {.status.availableReplicas} {.spec.replicas}{"\n"}{end}')
  log "$workloads"

  while IFS= read -r line; do
    workload_name=$(echo "$line" | awk '{print $1}')
    available_replicas=$(echo "$line" | awk '{print $2}')
    desired_replicas=$(echo "$line" | awk '{print $3}')

    # default available_replicas to 0 when empty
    if [ -z "$available_replicas" ]; then
      available_replicas=0
    fi
    assertEquals "$workload $workload_name: Available replicas should match desired replicas" "$desired_replicas" "$available_replicas"
    
  done <<< "$workloads"
}

testAllWorkloadsRunning() {
  checkWorkloadStatus "Statefulset"
  checkWorkloadStatus "Deployment"
}

testExpectedCRDSInstalled() {
  argocd_base_yaml="${PROJECT_DIR}/k8s-configs/cluster-tools/base/git-ops/argo/base/install.yaml"
  crd_names=($(yq eval 'select(.kind == "CustomResourceDefinition") | .metadata.name' $argocd_base_yaml ))

  for crd in "${crd_names[@]}"; do
    if [[ "$crd" == "---" ]]; then
      continue
    fi
    kubectl get crd "$crd" > /dev/null 2>&1
    assertEquals "Expected CRD: $crd missing" 0 $?
  done
}

testArgocdAppsCreated() {
  base_app="${CLUSTER_NAME}-${REGION}-${ENV_TYPE}"
  app_list=($(find "${PROJECT_DIR}" -type d -name "p1as-*" -exec basename {} \;))
  app_list=("${app_list[@]/#/$base_app-}")
  app_list+=("${base_app}")
  for app in "${app_list[@]}"; do
    kubectl get app -n argocd "${app}" > /dev/null 2>&1
    assertEquals "Expected app: ${app} missing" 0 $?
  done

}

# When arguments are passed to a script you must
# consume all of them before shunit is invoked
# or your script won't run.  For integration
# tests, you need this line.
shift $#

# load shunit
. ${SHUNIT_PATH}