#!/bin/bash

CI_SCRIPTS_DIR="${SHARED_CI_SCRIPTS_DIR:-/ci-scripts}"
. "${CI_SCRIPTS_DIR}"/common.sh "${1}"

if skipTest "${0}"; then
  log "Skipping test ${0}"
  exit 0
fi

## Running locally
# To run locally see the following example to set env vars and run the test:
# SELECTED_KUBE_NAME=ci-cd-9 \
#   SHARED_CI_SCRIPTS_DIR=/Users/jackminer/git/k8s-deploy-tools/ci-scripts \
#   SHUNIT_PATH=/Users/jackminer/Downloads/shunit2-2.1.8/shunit2 \
#   PCB_PATH=/Users/jackminer/git/ping-cloud-base \
#   ./tests/common/01-test-csr.sh

test_seal_sh() {
    # TODO: dupe some env vars from k8s-deploy-tools
    # SELECTED_KUBE_NAME comes from gitlab ci/cd - set manually if testing locally
    BRANCH="dev"
    export LOCAL="true"
    # If PCB_PATH provided use it, otherwise use CI_PROJECT_DIR set by Gitlab, since this pipeline is PCB's
    PCB_PATH=${PCB_PATH:-$CI_PROJECT_DIR}
    pushd /tmp
    git clone -b "${BRANCH}" codecommit://${SELECTED_KUBE_NAME}-cluster-state-repo
    pushd /tmp/${SELECTED_KUBE_NAME}-cluster-state-repo/k8s-configs
    ./seal.sh
    #cp /tmp/ping-secrets.yaml base/secrets.yaml
    #cp /tmp/sealed-secrets.yaml base/sealed-secrets.yaml
    num_secrets=$(grep -c "kind: Secret" /tmp/ping-secrets.yaml)
    num_sealed_secrets=$(grep -c "kind: SealedSecret" /tmp/sealed-secrets.yaml)
    assertEquals "Checking secret and sealed secret counts match" "${num_secrets}" "${num_sealed_secrets}"
    # DEBUG=true ./git-ops-command.sh us-west-2
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