#!/bin/bash

CI_SCRIPTS_DIR="${SHARED_CI_SCRIPTS_DIR:-/ci-scripts}"
. "${CI_SCRIPTS_DIR}"/common.sh "${1}"

if skipTest "${0}"; then
  log "Skipping test ${0}"
  exit 0
fi

## Running locally
# To run locally see the following example to set env vars and run the test:
# SELECTED_KUBE_NAME=ci-cd-SOME_NUM \
#   LOCAL="true"
#   ENV_TYPE="dev"
#   SHARED_CI_SCRIPTS_DIR=/PATH/TO/k8s-deploy-tools/ci-scripts \
#   SHUNIT_PATH=/PATH/TO/shunit2-2.1.8/shunit2 \
#   PCB_PATH=/PATH/TO/ping-cloud-base \
#   ./tests/common/01-test-csr.sh

test_seal_sh() {
    # TODO: copy this logic from k8s-deployt-ools/ci-scripts/k8s-deploy/deploy.sh
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

    pushd /tmp
    git clone -b "${branch_name}" codecommit://${SELECTED_KUBE_NAME}-cluster-state-repo
    pushd /tmp/${SELECTED_KUBE_NAME}-cluster-state-repo/k8s-configs
    ./seal.sh

    num_secrets=$(grep -c "kind: Secret" /tmp/ping-secrets.yaml)
    num_sealed_secrets=$(grep -c "kind: SealedSecret" /tmp/sealed-secrets.yaml)
    assertEquals "Checking secret and sealed secret counts match" "${num_secrets}" "${num_sealed_secrets}"

    # cp /tmp/ping-secrets.yaml base/secrets.yaml
    # cp /tmp/sealed-secrets.yaml base/sealed-secrets.yaml
    # ./git-ops-command.sh us-west-2 > /tmp/test-uber-output.yaml

    # grep "kind: Secret"
    popd
    popd
}

# When arguments are passed to a script you must
# consume all of them before shunit is invoked
# or your script won't run.  For integration
# tests, you need this line.
shift $#

# load shunit
. ${SHUNIT_PATH}