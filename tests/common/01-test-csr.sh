#!/bin/bash
# shellcheck disable=SC2164

CI_SCRIPTS_DIR="${SHARED_CI_SCRIPTS_DIR:-/ci-scripts}"
. "${CI_SCRIPTS_DIR}"/common.sh "${1}"

if skipTest "${0}"; then
  log "Skipping test ${0}"
  exit 0
fi

## Running locally
# To run locally see the following example to set env vars and run the test from the top level of ping-cloud-base:
# SELECTED_KUBE_NAME=ci-cd-SOME_NUM \
#   LOCAL="true"
#   ENV_TYPE="dev"
#   SHARED_CI_SCRIPTS_DIR=/PATH/TO/k8s-deploy-tools/ci-scripts \
#   SHUNIT_PATH=/PATH/TO/shunit2-2.1.8/shunit2 \
#   PCB_PATH=/PATH/TO/ping-cloud-base \
#   ./tests/common/01-test-csr.sh

setUp() {
    # NOTE: copy of logic from k8s-deploy-tools/ci-scripts/k8s-deploy/deploy.sh
    local branch_name=""
    if [[ ${ENV_TYPE} == "prod" ]]; then
        branch_name="master"
    else
        branch_name="${ENV_TYPE}"
    fi
    # Set LOCAL to true for seal.sh to pull the PCB_PATH properly
    export LOCAL="true"
    # If PCB_PATH is provided use it, otherwise use CI_PROJECT_DIR set by Gitlab, since PCB will already be checked out
    export PCB_PATH=${PCB_PATH:-$CI_PROJECT_DIR}

    cd /tmp || exit 1
    git clone -b "${branch_name}" codecommit://${SELECTED_KUBE_NAME}-cluster-state-repo
    cd /tmp/${SELECTED_KUBE_NAME}-cluster-state-repo/k8s-configs
    ./seal.sh
}

tearDown() {
    rm -rf /tmp/${SELECTED_KUBE_NAME}-cluster-state-repo
}

test_seal_secret_count_match() {
    # Test that the counts match of the secrets sealed vs the secrets which weren't sealed previously
    num_secrets=$(grep -c "kind: Secret" /tmp/ping-secrets.yaml)
    num_sealed_secrets=$(grep -c "kind: SealedSecret" /tmp/sealed-secrets.yaml)
    assertEquals "Checking secret and sealed secret counts match" "${num_secrets}" "${num_sealed_secrets}"
}

test_no_secret_in_uber_yaml() {
    # Copy the sealed secrets into the cluster-state-repo directory
    cp /tmp/ping-secrets.yaml base/secrets.yaml
    cp /tmp/sealed-secrets.yaml base/sealed-secrets.yaml

    # Re-run uber yaml output as seal.sh does not save its output
    local uber_yaml_output="/tmp/test-uber-output.yaml"
    echo "Generating uber yaml..."
    ./git-ops-command.sh us-west-2 > ${uber_yaml_output}

    # Test that there are no secrets in the uber yaml output
    # Find all kind: Secrets at the top level, ignoring karpenter-cert as it's managed by karpenter
    yq 'select(.kind == "Secret") | select(.metadata.name != "karpenter-cert")' ${uber_yaml_output} -e
    assertEquals "yq exit code should be 1 as no matches are found" 1 $?
}

# When arguments are passed to a script you must
# consume all of them before shunit is invoked
# or your script won't run.  For integration
# tests, you need this line.
shift $#

# load shunit
. ${SHUNIT_PATH}