#!/bin/bash

CI_SCRIPTS_DIR="${SHARED_CI_SCRIPTS_DIR:-/ci-scripts}"
. "${CI_SCRIPTS_DIR}"/common.sh "${1}"

if skipTest "${0}"; then
  log "Skipping test ${0}"
  exit 0
fi

testCertCreatedAndReady() {
    message=$(kubectl get certificate acme-tls-cert -n ping-cloud -o jsonpath='{.status.conditions[*].message}')
    assertEquals "Certificate acme-tls-cert is not ready" "Certificate is up to date and has not expired" "${message}"
}

testCertSecretHasThreeItems() {
    secret_data_len=$(kubectl get secret acme-tls-cert -n ping-cloud -o jsonpath='{.data}' | jq -r 'keys | length')
    assertEquals "Secret acme-tls-cert does not have three items" "3" "${secret_data_len}"
}

# When arguments are passed to a script you must
# consume all of them before shunit is invoked
# or your script won't run.  For integration
# tests, you need this line.
shift $#

# load shunit
. ${SHUNIT_PATH}