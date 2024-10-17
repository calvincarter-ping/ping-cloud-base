#!/bin/bash

CI_SCRIPTS_DIR="${SHARED_CI_SCRIPTS_DIR:-/ci-scripts}"
. "${CI_SCRIPTS_DIR}/common.sh" "${1}"

if skipTest "${0}"; then
  log "Skipping test ${0}"
  exit 0
fi

THIS_TEST=$(basename "$0")
UBER_YAML_OUTPUT="/tmp/${THIS_TEST}/test-uber-output.yaml"

setUp() {
  local this_test
  this_test="$(basename "$0")"
  local csr_path="/tmp/${this_test}/test-csr"
  local csr_name=${CLUSTER_STATE_REPO_URL##*\/}

  ## Special env setup for git-ops-command.sh to work properly in these tests ##
  # Set LOCAL for to pull the PCB_PATH properly
  export LOCAL="true"
  # Use PROJECT_DIR if provided manually, otherwise use CI_PROJECT_DIR set by Gitlab,
  # since PCB will already be checked out
  export PCB_PATH=${PROJECT_DIR:-$CI_PROJECT_DIR}

  # Remove CSR if it exists, moved from tearDown as pwd errors were occurring
  rm -rf "${csr_path}"

  # NOTE: copy of logic from k8s-deploy-tools/ci-scripts/k8s-deploy/deploy.sh
  local branch_name=""
  if [[ ${ENV_TYPE} == "prod" ]]; then
    branch_name="master"
  else
    branch_name="${ENV_TYPE}"
  fi

  mkdir -p "${csr_path}"
  cd "${csr_path}" || exit 1
  git clone -b "${branch_name}" "codecommit://${csr_name}" .
  cd k8s-configs || exit 1
  log "Generating uber yaml, this may take some time..."
  ./git-ops-command.sh "${REGION}" > "${UBER_YAML_OUTPUT}"
}

testNGINXVersionMatch() {
  export nginx_expected_version="1.11.2"
  yq -e 'select(.metadata.labels."app.kubernetes.io/name" == "ingress-nginx") | select(.metadata.labels."app.kubernetes.io/version" != env(nginx_expected_version))' "${UBER_YAML_OUTPUT}"
  assertEquals "Some matches were found matching a version other than expected, see output from yq above^^" 1 $?
}

# When arguments are passed to a script you must
# consume all of them before shunit is invoked
# or your script won't run.  For integration
# tests, you need this line.
shift $#

# load shunit
. ${SHUNIT_PATH}