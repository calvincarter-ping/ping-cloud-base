#!/bin/bash

CI_SCRIPTS_DIR="${SHARED_CI_SCRIPTS_DIR:-/ci-scripts}"
. "${CI_SCRIPTS_DIR}/common.sh" "${1}"

if skipTest "${0}"; then
  log "Skipping test ${0}"
  exit 0
fi

## Common Methods

get_nlb_service() {
  type=$1
  # Get ingress URL to avoid hardcoding it
  nginx_service_url=$(kubectl get service ingress-nginx -n "ingress-nginx-${type}" -o jsonpath='{.status.loadBalancer.ingress[*].hostname}')
  assertNotNull "NGINX service load balancer URL was unexpectedly null!" "${nginx_service_url}"
  log "Got 'ingress-nginx' ${type} service URL: ${nginx_service_url}"

  # Make a request against the URL, check the response code is 200
  # Retry because nginx is restarting during this time...
  nginx_service_resp_code=$(curl -k -s "https://${nginx_service_url}" -o /dev/null -w "%{http_code}")
  if [[ "${nginx_service_resp_code}" == "000" ]]; then
    log "Error - Received response 000, curling with verbose before exiting..."
    curl -v -k "https://${nginx_service_url}" -o /dev/null
    exit 1
  fi

  # When going directly to the service, we should get a 404 from NGINX. This tests NGINX directly while removing
  # dependencies on underlying applications which might have issues (metadata service, pa-was, etc...)
  assertEquals "NGINX service ${type} response code was not 404" "404" "${nginx_service_resp_code}"
}

check_configmap_key_exists() {
  namespace=$1
  configmap=$2
  key=$3
  assertTrue "Configmap '${configmap}' in namespace '${namespace}' missing key '${key}'" \
    kubectl get cm "${configmap}" -n "${namespace}" -o yaml | yq -e ".data.${key}"
}

## Tests

testNginxIngressClass(){
    log "Checking number of ingress classes"
    # Use xargs for whitespace trimming...
    num_ingress_classes=$(kubectl get ingressclass -A -o json | jq -r '.items[].metadata.name' | wc -l | xargs)
    expected_num_ingress_classes=2
    assertEquals "Number of ingress classes should have been two - public and private" "${num_ingress_classes}" "${expected_num_ingress_classes}"
}

testNginxPrivateNlbService404(){
  get_nlb_service "private"
}

testNginxPublicNlbService404(){
  get_nlb_service "public"
}

testNginxPrivateLogsForErrors(){
  # Default cert error is a race condition waiting for cert manager to retrieve the acme cert
  # Error while validating is due to known error where ingress watches other ingress classes, even in other namespaces
  exceptions="(Error loading custom default certificate|Ignoring ingress because of error while validating ingress class)"
  error_regex="(error|fatal|exception)"

  log "Checking private logs for errors, minus these exceptions: ${exceptions}"

  kubectl logs -l app.kubernetes.io/role=ingress-nginx-private -n ingress-nginx-private --tail=200 --all-containers=true --timestamps \
    | grep -iE "${error_regex}" \
    | grep -vE "${exceptions}"
  assertEquals "Found errors in NGINX logs" 1 $?
}

testNginxPublicLogsForErrors(){
  # Default cert error is a race condition waiting for cert manager to retrieve the acme cert
  # Error while validating is due to known error where ingress watches other ingress classes, even in other namespaces
  # Connection issues are due to a race condition when starting between sigsci agent and nginx
  exceptions="(Error loading custom default certificate|Ignoring ingress because of error while validating ingress class|cannot connect uds socket|Failed to open connection to agent)"
  error_regex="(error|fatal|exception)"

  log "Checking public logs for errors, minus these exceptions: ${exceptions}"

  kubectl logs -l app.kubernetes.io/role=ingress-nginx-public -n ingress-nginx-public --tail=200 --all-containers=true --timestamps \
    | grep -iE "${error_regex}" \
    | grep -vE "${exceptions}"
  assertEquals "Found errors in NGINX logs" 1 $?
}

testNginxSigSciModule() {
  command_to_run="grep sigsci_module /etc/nginx/nginx.conf"
  log "Checking for SigSci module loaded in config at /etc/nginx/nginx.conf"
  kubectl exec -ti -n ingress-nginx-public deployment/nginx-ingress-controller -c nginx-ingress-controller -- ${command_to_run}
  assertEquals "Module not found in NGINX public" 0 $?
}

testSigSciVersion() {
  # NOTE: Version must be updated each time we upgrade SigSci... at least for now
  sigsci_expected_version="4.57.0"
  command_to_run="/home/sigsci/sigsci-agent --version"
  log "Checking SigSci version in SigSci agent container against expected version: ${sigsci_expected_version}"
  sigsci_found_version=$(kubectl exec -ti -n ingress-nginx-public deployment/nginx-ingress-controller -c sigsci-agent -- ${command_to_run})
  # Remove carriage returns from output
  command_filtered=$(echo "${sigsci_found_version}" | sed -e 's/\r//g')
  assertEquals "Correct SigSci version not found" "${sigsci_expected_version}" "${command_filtered}"
}

testNginxPublicConfigMap() {
  kubectl get cm nginx-configuration -n ingress-nginx-public -o yaml | yq -e '.data.location-snippet'
  kubectl get cm nginx-configuration -n ingress-nginx-public -o yaml | yq -e '.data.log-format-upstream'
  kubectl get cm nginx-configuration -n ingress-nginx-public -o yaml | yq -e '.data.main-snippet'
  kubectl get cm nginx-configuration -n ingress-nginx-public -o yaml | yq -e '.data.max-worker-connections'
  kubectl get cm nginx-configuration -n ingress-nginx-public -o yaml | yq -e '.data.sll-ciphers'
  kubectl get cm nginx-configuration -n ingress-nginx-public -o yaml | yq -e '.data.ssl-dh-param'
  kubectl get cm nginx-configuration -n ingress-nginx-public -o yaml | yq -e '.data.worker-processes'
}

# When arguments are passed to a script you must
# consume all of them before shunit is invoked
# or your script won't run.  For integration
# tests, you need this line.
shift $#

# load shunit
. ${SHUNIT_PATH}