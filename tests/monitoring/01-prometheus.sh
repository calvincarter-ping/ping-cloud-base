#!/bin/bash

CI_SCRIPTS_DIR="${SHARED_CI_SCRIPTS_DIR:-/ci-scripts}"
. "${CI_SCRIPTS_DIR}"/common.sh "${1}"

if skipTest "${0}"; then
  log "Skipping test ${0}"
  exit 0
fi

# Verify the Prometheus server API is reachable via its externally exposed URL.
testPrometheusAPIAccessible() {
  log "Checking Prometheus API via /api/v1/status/runtimeinfo"
  
  status=$(curl -k -s -o /dev/null -w "%{http_code}" \
    "${PROMETHEUS}/api/v1/status/runtimeinfo" 2>/dev/null)
  
  assertEquals "Prometheus API should return 200 OK" "200" "${status}"
}

# Verify each agent scrape job has active targets collecting valid data.
# Queries up{job="<name>"} per job — Prometheus sets up=1 for every successful scrape.
# Covers all jobs defined in p1as-prometheus-agent values.yaml.
testPrometheusAgentJobsCollectingData() {
  log "Verifying each agent scrape job has active targets via up metric"

  expected_jobs="prometheus kube-state-metrics kubernetes-apiservers kubernetes-nodes kubernetes-pods kubernetes-cadvisor kubernetes-service-endpoints opensearch-service"

  for job in ${expected_jobs}; do
    response=""
    value=""
    for i in {1..10}; do
      encoded_job=$(echo "up{job=\"${job}\"}" | sed 's/{/%7B/g;s/}/%7D/g;s/"/%22/g')
      response=$(curl -k -s "${PROMETHEUS}/api/v1/query?query=${encoded_job}" 2>/dev/null)
      result_count=$(echo "${response}" | jq '.data.result | length' 2>/dev/null)
      if [[ ${result_count} -gt 0 ]]; then
        value=$(echo "${response}" | jq -r '.data.result[0].value[1]' 2>/dev/null)
        if [[ "${value}" == "1" ]]; then
          log "Job '${job}': up=1 (target active and scraping successfully)"
          break
        fi
      fi
      log "Attempt ${i}/10 - waiting for up=1 for job: ${job}..."
      sleep 10
    done
    assertNotNull "Job '${job}' should have up=1 (target active and scraping)" "${value}"
    assertEquals "Job '${job}' up metric should be 1" "1" "${value}"
  done
}

testPrometheusJobExporterRunning() {
  POD=$(kubectl -n prometheus get pods -l app=prometheus-job-exporter -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
  test -n "$POD" && kubectl -n prometheus get pod "$POD" -o jsonpath='{.status.phase}' | grep -q "Running"
  assertEquals "Prometheus job exporter pod not running" 0 $?
}

# Verify external labels are correctly resolved and attached to remote-written metrics.
# When the agent remote-writes metrics to the server, each metric should include
# k8s_cluster_name and k8s_cluster_region in its labels (via expand-external-labels).
# This test queries kube_node_info from the kube-state-metrics job and verifies
# the external labels are present in the metric result.
testPrometheusExternalLabelsPresent() {
  log "Verifying k8s_cluster_name and k8s_cluster_region labels are attached to remote-written metrics"

  # Query kube_node_info — reliable metric from kube-state-metrics job
  response=""
  for i in {1..10}; do
    response=$(curl -k -s \
      'http://localhost:9090/api/v1/query?query=kube_node_info' 2>/dev/null)
    result_count=$(echo "${response}" | jq '.data.result | length' 2>/dev/null)
    if [[ ${result_count} -gt 0 ]]; then
      # Extract external label values from the metric result
      k8s_cluster_name=$(echo "${response}" | jq -r '.data.result[0].metric.k8s_cluster_name // ""')
      k8s_cluster_region=$(echo "${response}" | jq -r '.data.result[0].metric.k8s_cluster_region // ""')
      log "External labels on kube_node_info metric — k8s_cluster_name: '${k8s_cluster_name}' | k8s_cluster_region: '${k8s_cluster_region}'"
      break
    fi
    log "Attempt ${i}/10 - waiting for kube_node_info metric with labels..."
    sleep 10
  done

  # Validate labels are present and not empty
  assertNotNull "k8s_cluster_name label must be present on remote-written metrics" "${k8s_cluster_name}"
  assertNotNull "k8s_cluster_region label must be present on remote-written metrics" "${k8s_cluster_region}"

  if [[ -z "${k8s_cluster_name}" ]]; then
    assertEquals "k8s_cluster_name label must be set with actual cluster name" "${k8s_cluster_name}" "ACTUAL_VALUE_EXPECTED"
  fi
  if [[ -z "${k8s_cluster_region}" ]]; then
    assertEquals "k8s_cluster_region label must be set with actual region" "${k8s_cluster_region}" "ACTUAL_VALUE_EXPECTED"
  fi
}

# Verify users_count metrics from the prometheus-job-exporter are present.
# The job exporter runs ldapsearch commands against PingDirectory pods (pingdirectory-0)
# to count users and exposes them as metrics. Scraped by agent's kubernetes-pods job.
testPrometheusJobExporterMetricsScraped() {
  log "Verifying users_count metrics from Job Exporter are present in Prometheus server"

  for i in {1..10}; do
    response=$(curl -k -s "${PROMETHEUS}/api/v1/query?query=users_count_1" 2>/dev/null)
    if echo "${response}" | grep -q '"resultType":"vector"'; then
      count=$(echo "${response}" | jq -r '.data.result[0].value[1] // "unknown"' 2>/dev/null)
      log "users_count_1 present in Prometheus server — value: ${count}"
      break
    fi
    log "Attempt ${i}/10 - waiting for users_count_1..."
    sleep 10
  done

  result_count=$(echo "${response}" | jq '.data.result | length' 2>/dev/null)
  assertNotEquals "users_count_1 should have at least one result in Prometheus server (non-empty data.result)" \
    "0" "${result_count}"
}

# Verify opensearch_cluster_status metric is scraped from OpenSearch service.
# Proves agent authentication and scraping of OpenSearch is working.
testPrometheusOpenSearchMetricsScraped() {
  log "Verifying opensearch_cluster_status metric is present in Prometheus server"

  for i in {1..10}; do
    response=$(curl -k -s "${PROMETHEUS}/api/v1/query?query=opensearch_cluster_status" 2>/dev/null)
    if echo "${response}" | grep -q '"resultType":"vector"'; then
      os_status=$(echo "${response}" | jq -r '.data.result[0].value[1] // "unknown"' 2>/dev/null)
      cluster=$(echo "${response}" | jq -r '.data.result[0].metric.cluster // "unknown"' 2>/dev/null)
      log "opensearch_cluster_status present — cluster: ${cluster}, status: ${os_status}"
      break
    fi
    log "Attempt ${i}/10 - waiting for opensearch_cluster_status..."
    sleep 10
  done

  result_count=$(echo "${response}" | jq '.data.result | length' 2>/dev/null)
  assertNotEquals "opensearch_cluster_status should have at least one result in Prometheus server (non-empty data.result)" \
    "0" "${result_count}"
}

# When arguments are passed to a script you must
# consume all of them before shunit is invoked
# or your script won't run.  For integration
# tests, you need this line.
shift $#

# load shunit
. ${SHUNIT_PATH}

