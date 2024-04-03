#!/bin/bash

CI_SCRIPTS_DIR="${SHARED_CI_SCRIPTS_DIR:-/ci-scripts}"
. "${CI_SCRIPTS_DIR}"/common.sh "${1}"
. "${CI_SCRIPTS_DIR}"/test/test_utils.sh

if skipTest "${0}"; then
  log "Skipping test ${0}"
  exit 0
fi

oneTimeSetUp(){
  # Save off CSD upload file in case test does not complete and leaves it with 1 or more 'exit 1' statements inserted into it
  kubectl exec pingaccess-admin-0 -c pingaccess-admin -n ping-cloud -- sh -c 'cp /opt/staging/hooks/82-upload-csd-s3.sh /tmp/82-upload-csd-s3.sh'
  kubectl exec pingaccess-0 -c pingaccess -n ping-cloud -- sh -c 'cp /opt/staging/hooks/82-upload-csd-s3.sh /tmp/82-upload-csd-s3.sh'

}
oneTimeTearDown(){
  # Revert the original file back when tests are done execting
  kubectl exec pingaccess-admin-0 -c pingaccess-admin -n ping-cloud -- sh -c 'cp /tmp/82-upload-csd-s3.sh /opt/staging/hooks/82-upload-csd-s3.sh'
  kubectl exec pingaccess-0 -c pingaccess -n ping-cloud -- sh -c 'cp /tmp/82-upload-csd-s3.sh /opt/staging/hooks/82-upload-csd-s3.sh'
}

testPingAccessRuntimeCsdUpload() {
  csd_upload "pingaccess" "${PROJECT_DIR}"/k8s-configs/ping-cloud/base/pingaccess/engine/aws/periodic-csd-upload.yaml
  assertEquals 0 $?
}

testPingAccessAdminCsdUpload() {
  csd_upload "pingaccess-admin" "${PROJECT_DIR}"/k8s-configs/ping-cloud/base/pingaccess/admin/aws/periodic-csd-upload.yaml
  assertEquals 0 $?
}

testPingAccessRuntimeCsdUploadCapturesFailure(){
  init_csd_upload_failure "pingaccess" 5 "${PROJECT_DIR}"/k8s-configs/ping-cloud/base/pingaccess/engine/aws/periodic-csd-upload.yaml
  assertEquals "CSD upload job should not have succeeded" 1 $?
}

testPingAccessAdminRuntimeCsdUploadCapturesFailure(){
  init_csd_upload_failure "pingaccess-admin" 5 "${PROJECT_DIR}"/k8s-configs/ping-cloud/base/pingaccess/admin/aws/periodic-csd-upload.yaml
  assertEquals "CSD upload job should not have succeeded" 1 $?
}

csd_upload() {
  local upload_csd_job_name="${1}-periodic-csd-upload"
  local upload_job="${2}"

  log "Applying the CSD upload job"
  log "Checking if there is an existing csd-upload-job"  
  kubectl delete -f "${upload_job}" -n "${PING_CLOUD_NAMESPACE}"

  kubectl apply -f "${upload_job}" -n "${PING_CLOUD_NAMESPACE}"
  assertEquals "The kubectl apply command to create the ${upload_csd_job_name} should have succeeded" 0 $?

  kubectl create job --from=cronjob/${upload_csd_job_name} ${upload_csd_job_name} -n "${PING_CLOUD_NAMESPACE}"
  assertEquals "The kubectl create command to create the job should have succeeded" 0 $?

  log "Waiting for CSD upload job to complete..."
  kubectl wait --for=condition=complete --timeout=900s job.batch/${upload_csd_job_name} -n "${PING_CLOUD_NAMESPACE}"
  assertEquals "The kubectl wait command for the job should have succeeded" 0 $?

  sleep 5

  log "Expected CSD files:"
  expected_csd_files "${upload_csd_job_name}" "^2.*support-data.zip$" | tee /tmp/expected.txt

  if ! verify_upload_with_timeout "pingaccess"; then
    return 1
  fi
  return 0
}

# When arguments are passed to a script you must
# consume all of them before shunit is invoked
# or your script won't run.  For integration
# tests, you need this line.
shift $#

# load shunit
. ${SHUNIT_PATH}