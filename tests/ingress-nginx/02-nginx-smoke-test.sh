#!/bin/bash

CI_SCRIPTS_DIR="${SHARED_CI_SCRIPTS_DIR:-/ci-scripts}"
. "${CI_SCRIPTS_DIR}/common.sh" "${1}"

if skipTest "${0}"; then
  log "Skipping test ${0}"
  exit 0
fi

### Basic tests to check that NGINX is working properly ###

testNginxIngressClass(){
    echo "Checking num ingresses..."
    # Use xargs for whitespace trimming...
    num_ingress_classes=$(kubectl get ingressclass -A -o json | jq -r '.items[].metadata.name' | wc -l | xargs)
    expected_num_ingress_classes=2
    assertEquals "Number of ingress classes should have been two - public and private" "${num_ingress_classes}" "${expected_num_ingress_classes}"
}

testMetadataEndpointReturns(){
  # Get ingress URL to avoid hardcoding it
  metadata_url=$(kubectl get ingress metadata-ingress -n ping-cloud -o jsonpath='{.spec.rules[*].host}')
  assertNotNull "Metadata ingress URL was unexpectedly null!" "${metadata_url}"

  # Make a request against the URL, check the response code is 200
  metadata_resp_code=$(curl -s "https://${metadata_url}" -o /dev/null -w "%{http_code}")
  assertEquals "Metadata response code was not 200" "200" "${metadata_resp_code}"
}

# When arguments are passed to a script you must
# consume all of them before shunit is invoked
# or your script won't run.  For integration
# tests, you need this line.
shift $#

# load shunit
. ${SHUNIT_PATH}