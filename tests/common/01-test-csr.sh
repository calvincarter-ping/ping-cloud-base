#!/bin/bash

CI_SCRIPTS_DIR="${SHARED_CI_SCRIPTS_DIR:-/ci-scripts}"
. "${CI_SCRIPTS_DIR}"/common.sh "${1}"

if skipTest "${0}"; then
  log "Skipping test ${0}"
  exit 0
fi

test_seal_sh() {
    # TODO: dupe some env vars from k8s-deploy-tools
    # SELECTED_KUBE_NAME comes from gitlab ci/cd - set manually if testing locally
    BRANCH="dev"
    export LOCAL="true"
    cd /tmp
    git clone -b "${BRANCH}" codecommit://${SELECTED_KUBE_NAME}-cluster-state-repo
    cd /tmp/${SELECTED_KUBE_NAME}-cluster-state-repo/k8s-configs
    ./seal.sh
}

# When arguments are passed to a script you must
# consume all of them before shunit is invoked
# or your script won't run.  For integration
# tests, you need this line.
shift $#

# load shunit
. ${SHUNIT_PATH}