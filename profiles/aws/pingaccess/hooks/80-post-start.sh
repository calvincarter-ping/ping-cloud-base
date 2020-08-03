#!/usr/bin/env sh

. "${HOOKS_DIR}/pingcommon.lib.sh"
. "${HOOKS_DIR}/utils.lib.sh"

"${VERBOSE}" && set -x

if test "${OPERATIONAL_MODE}" != "CLUSTERED_CONSOLE"; then
  beluga_log "post-start: skipping post-start on engine"
  exit 0
fi

echo "post-start: pingaccess config settings"
export_config_settings

# Remove the marker file before running post-start initialization.
POST_START_INIT_MARKER_FILE="${OUT_DIR}/instance/post-start-init-complete"
rm -f "${POST_START_INIT_MARKER_FILE}"

# Wait until pingaccess admin localhost is available
pingaccess_admin_wait

# ADMIN_CONFIGURATION_COMPLETE is used as a marker file that tracks if server was initially configured.
#
# If ADMIN_CONFIGURATION_COMPLETE does not exist then set initial configuration.
ADMIN_CONFIGURATION_COMPLETE=${OUT_DIR}/instance/ADMIN_CONFIGURATION_COMPLETE
if ! test -f "${ADMIN_CONFIGURATION_COMPLETE}"; then
  echo "post-start: ${ADMIN_CONFIGURATION_COMPLETE} not present"

  echo "post-start: Starting hook: ${HOOKS_DIR}/81-import-initial-configuration.sh"
  sh "${HOOKS_DIR}/81-import-initial-configuration.sh"
  if test $? -ne 0; then
    exit 1
  fi

  if isPingaccessWas; then
    sh "${HOOKS_DIR}/82-configure-p14c-token-provider.sh"
    if test $? -ne 0; then
      exit 1
    fi

    sh "${HOOKS_DIR}/83-configure-initial-pa-was.sh"
    if test $? -ne 0; then
      exit 1
    fi

  fi

  touch ${ADMIN_CONFIGURATION_COMPLETE}

# Since this isn't initial deployment, change password if from disk is different than the desired value.
elif test $(comparePasswordDiskWithVariable) -eq 0; then

  echo "post-start: changing PA admin password"
  changePassword

else
  echo "post-start: not changing PA admin password"
fi

# Update the admin config host
echo "Updating the host and port of the Admin Config..."
update_admin_config_host_port

echo "post-start: Starting hook: ${HOOKS_DIR}/82-add-acme-cert.sh"
sh "${HOOKS_DIR}/82-add-acme-cert.sh"
test $? -ne 0 && exit 1

# Upload a backup right away after starting the server.
echo "post-start: Starting hook: ${HOOKS_DIR}/90-upload-backup-s3.sh"
sh "${HOOKS_DIR}/90-upload-backup-s3.sh"
BACKUP_STATUS=${?}

beluga_log "post-start: data backup status: ${BACKUP_STATUS}"

# Write the marker file if post-start succeeds.
if test "${BACKUP_STATUS}" -eq 0; then
  touch "${POST_START_INIT_MARKER_FILE}"
  exit 0
fi

# Kill the container if post-start fails.
beluga_log "post-start: admin post-start backup failed"
"${STOP_SERVER_ON_FAILURE}" && stop_server || exit 1