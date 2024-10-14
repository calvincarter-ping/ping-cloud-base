#!/bin/sh

# Variables
BACKUP_NAME="pingdirectory-backup"
NAMESPACE="ping-cloud"
SCRIPT="/opt/in/backup-ops.sh"
SKIP_RESOURCE_CLEANUP="false"

# Functions
# Function to get the full pod name based on the prefix name 'pingdirectory-backup'
get_pod_name() {
  kubectl get pods -n "${NAMESPACE}" --no-headers -o custom-columns=":metadata.name" | grep "^${BACKUP_NAME}" | head -n 1
}

# Function to check determine when a Job is complete
is_job_complete() {
  kubectl get job "${BACKUP_NAME}" -n "${NAMESPACE}" -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' | grep -qi True
}

# Function to get the number of failed attempts of Job
get_failed_attempts() {
  kubectl get job "${BACKUP_NAME}" -n "${NAMESPACE}" -o jsonpath='{.status.failed}' 2>/dev/null
}

# Function to get the number of backofflimits/# of retries for Job
get_backoff_limit() {
  kubectl get job "${BACKUP_NAME}" -n "${NAMESPACE}" -o jsonpath='{.spec.backoffLimit}'
}

# Function to delete Job and its PVC if detected in cluster
cleanup_resources() {
  if [ "${SKIP_RESOURCE_CLEANUP}" = "true" ]; then
    return 0
  fi

  # Remove Job and PVC if found in cluster
  kubectl get job "${BACKUP_NAME}" -n "${NAMESPACE}" > /dev/null 2>&1
  if [ "$?" -eq "0" ]; then
    echo "Deleting job ${BACKUP_NAME}..."
    kubectl delete job "${BACKUP_NAME}" -n "${NAMESPACE}"
  fi
  kubectl get pvc "${BACKUP_NAME}" -n "${NAMESPACE}" > /dev/null 2>&1
  if [ "$?" -eq "0" ]; then
    echo "Deleting PVC ${BACKUP_NAME}..."
    kubectl delete pvc "${BACKUP_NAME}" -n "${NAMESPACE}"
  fi
}

check_if_another_backup_is_running() {
    # Determine if Cronjob is Active.
    num_of_active_cronjobs=$(kubectl get cronjob pingdirectory-periodic-backup -n "${NAMESPACE}" -o jsonpath='{.status.active}' 2>/dev/null)

    if [ -n "${num_of_active_cronjobs}" ]; then

        # Entering this condition means there is an active Cronjob running.

        # Determine if Manual Job is also running while Cronjob is running.
        # Manual jobs can be found by filtering on "manual=true" label.
        active_manual_job_name=$(kubectl get jobs --selector=manual=true -o jsonpath='{.items[0].metadata.name}' -n "${NAMESPACE}" 2>/dev/null)

        if [ -z "${active_manual_job_name}" ]; then
            echo "Exiting because a manual Job was not found. There is not collision with Cronjob and manual Job."
            return 0
        fi

        # Manual Job has been detected and is running.
        # Lets now get the Cronjob name because we'll need to determine who ran first at this point.
        # Is it the Cronjob or Job?
        # Get CronJob name
        # CronJob names will always begin with "pingdirectory-periodic-backup"
        active_cronjob_job_name=$(kubectl get jobs -o jsonpath='{.items[0].metadata.name}' -n "${NAMESPACE}" 2>/dev/null | grep 'pingdirectory-periodic-backup-' | tail -n 1)

        # Now that we have both names (Cronjob and manual Job).
        # We can sort the create timestamp and determine who ran first (Cronjob or manual Job).
        second_job_by_name=$(kubectl get job "${active_cronjob_job_name}" "${active_manual_job_name}" --sort-by=.metadata.creationTimestamp -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' -n "${NAMESPACE}" 2>/dev/null | sed -n '2p')

        # Avoid interrupting backup that started first. Delete the second backup only.
        echo "There is a backup already running at the moment. Terminating ${second_job_by_name} Job"

        # Before deleting this Job pause so BeOps can see logs.
        sleep 30

        # Terminate 2nd Job
        kubectl delete job "${second_job_by_name}" -n "${NAMESPACE}"

    else

        # Entering this condition means there is NOT an active Cronjob running.

        # Determine if there is another Manual Job running. We also need to avoid 2 manual Jobs from running.
        # Manual jobs can be found by filtering on "manual=true" label.
        # We can sort the create timestamp and retrieve the 2nd manual Job if there is any.
        second_manual_job_by_name=$(kubectl get job --selector=manual=true --sort-by=.metadata.creationTimestamp -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' -n "${NAMESPACE}" 2>/dev/null | sed -n '2p')

        if [ -z "${second_manual_job_by_name}" ]; then
            echo "Exiting because a second manual Job was not found"
            return 0
        fi

        # Avoid interrupting manual backup Job that started first. Delete the second backup only.
        echo "There is a manual backup already running at the moment. Terminating ${second_manual_job_by_name} Job"

        # Before deleting this Job pause so BeOps can see logs.
        sleep 30

        # Terminate 2nd Job
        kubectl delete job "${second_manual_job_by_name}" -n "${NAMESPACE}"
    fi

    return 1 # Default, exit method as there is another backup running.
             # This should never happen if there is not collision with Cronjob and manual Job.
}

### Script execution begins here. ###

# This guarantees that cleanup_resources method will always run, even if the script exits due to an error
trap "cleanup_resources" EXIT

if ! check_if_another_backup_is_running; then
  # Prepare to exit because there is a CronJob/manual Job collision.
  # Avoid cleaning up resources because the 1st Job actually is using the PVC.
  SKIP_RESOURCE_CLEANUP="true"
  exit 0 # Exit graceful. Technically, this is not a backup error.
fi

# Before backup begins. Ensure lingering resources of Job and PVC have been removed when running prior backup
cleanup_resources

# Execute backup-ops.sh script (which kicks off the k8s pingdirectory-backup Job)
test -x ${SCRIPT} && ${SCRIPT} "scheduled-cronjob"

# Wait for Job to be in 'Complete' state
while true; do

  # Verify the pod of the Job has been deployed before checking Job state.
  POD_NAME=$(get_pod_name)
  if [ -z "${POD_NAME}" ]; then
    echo "Pod with prefix ${BACKUP_NAME} not found. Waiting for ${BACKUP_NAME} Job to deploy..."
  else

    # The pod of the Job is running. The following logic will now check for completion on the Job K8s object
    if is_job_complete; then
      echo "${BACKUP_NAME} Job successfully completed. Cronjob will clean up the backup job PVC and Job resources"
      exit 0
    else

      # Job is not complete yet once in this else condition.

      # Now, check to ensure Job backofflimit/retries hasn't exceeded.
      # If so, immediately terminate Cronjob with error as its retries of backup Job has exceeded.
      # As of now we have backofflimit set to 0 in K8s Job 'pingdirectory-backup' so technically we shouldn't need this logic.
      # However, if this were to ever change. The cronjob is smart enough to keep Job and PVC until it has exceeded
      # its backofflimit/retry attempts of producing a backup.


      # Retrieve failed attempts of Job if exist and collect backofflimit/# of retries from Job K8s spec
      failed_attempts=$(get_failed_attempts)
      backoff_limit=$(get_backoff_limit)

      # If we can't find any failures assume Job is still running
      if [ -z "${failed_attempts}" ]; then
        echo "${BACKUP_NAME} Job is running but not complete. Waiting..."

      # Failed attempts was found check to see if it exceeds backofflimit. If so, we can stop the cronjob and report
      # as an error
      elif [ "${failed_attempts}" -ge "${backoff_limit}" ]; then
        echo "Job failed ${failed_attempts} times, with backofflimit of ${backoff_limit}. Job has exceeded its backofflimit/retries. Exiting with error..."
        echo "Cronjob will clean up the backup job PVC and Job resources"
        exit 1

      # Failed attempts have not exceeded. This means K8s Job pingdirectory-backup backofflimit hasn't exceeded so
      # The cronjob should be aware and avoid deleting the Job and PVC. Cronjob will continue to wait until backofflimit
      # has exceeded or until a successful completion of backup.
      else
        echo "Job failed ${failed_attempts} times, with backofflimit of ${backoff_limit}. ${BACKUP_NAME} Job is expected to retry."
      fi
    fi
  fi

  sleep 5  # Wait for 5 seconds before checking again
done