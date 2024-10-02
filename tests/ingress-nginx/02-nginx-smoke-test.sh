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

testNGINXService404(){
  # Get ingress URL to avoid hardcoding it
  nginx_service_url=$(kubectl get service ingress-nginx -n ingress-nginx-public -o jsonpath='{.status.loadBalancer.ingress[*].hostname}')
  assertNotNull "NGINX service load balancer URL was unexpectedly null!" "${nginx_service_url}"
  echo "Got nginx service URL: ${nginx_service_url}"

  # Make a request against the URL, check the response code is 200
  # Retry because nginx is restarting during this time...
  nginx_service_resp_code=$(curl -k -s "https://${nginx_service_url}" -o /dev/null -w "%{http_code}")
  if [[ "${nginx_service_resp_code}" == "000" ]]; then
    echo "Error - Received response 000, curling with verbose before exiting..."
    curl -v -k "https://${nginx_service_url}" -o /dev/null
    exit 1
  fi

  # When going directly to the service, we should get a 404 from NGINX. This tests NGINX directly while removing
  # dependencies on underlying applications which might have issues (metadata service, pa-was, etc...)
  assertEquals "NGINX service response code was not 404" "404" "${nginx_service_resp_code}"
}

# When arguments are passed to a script you must
# consume all of them before shunit is invoked
# or your script won't run.  For integration
# tests, you need this line.
shift $#

# load shunit
. ${SHUNIT_PATH}