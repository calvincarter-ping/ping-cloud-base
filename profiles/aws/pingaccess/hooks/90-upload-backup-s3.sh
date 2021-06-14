#!/usr/bin/env sh

. "${HOOKS_DIR}/pingcommon.lib.sh"
. "${HOOKS_DIR}/utils.lib.sh"

"${VERBOSE}" && set -x

beluga_log "Uploading to location ${BACKUP_URL}"

# Set required environment variables for skbn
initializeSkbnConfiguration "${PA_DATA_BACKUP_URL}"

DST_DIRECTORY=$(mktemp -d)
cd ${DST_DIRECTORY}

# Make request to admin API and backup latest data
make_api_request_download -OJ -X GET https://localhost:9000/pa-admin-api/v3/backup
test $? -ne 0 && exit 1

# Get the name of the backup file
DST_FILE=$(find ./ -iname \*.zip)
DST_FILE=${DST_FILE#./}

# Validate admin API call was successful and that zip isn't corrupted
if test $(unzip -t "${DST_FILE}" &> /dev/null; echo $?) -ne 0 ; then
  # Cleanup k8s-s3-upload-archive temp directory
  beluga_log "Failed to export archive"
  rm -rf ${DST_DIRECTORY}
  exit 1
fi

UPLOAD_DIR="$(mktemp -d)"

# Append the current timestamp to zip filename
DST_FILE_TIMESTAMP="data-$(date +%m-%d-%Y.%H.%M.%S).zip"

mv "${DST_FILE}" "${UPLOAD_DIR}/${DST_FILE_TIMESTAMP}"

# Cleanup backup dir
cd "${UPLOAD_DIR}" || exit 1
rm -rf "${DST_DIRECTORY}"

# Two copy of the backup will be pushed to cloud storage.
# Make a copy: latest.zip
DST_FILE_LATEST="latest.zip"
cp "${UPLOAD_DIR}/${DST_FILE_TIMESTAMP}" "${UPLOAD_DIR}/${DST_FILE_LATEST}"

beluga_log "Copying files in '${UPLOAD_DIR}' to '${SKBN_CLOUD_PREFIX}'"

if ! skbnCopy "${UPLOAD_DIR}" "${SKBN_CLOUD_PREFIX}"; then
  beluga_log "Failed to upload files in ${UPLOAD_DIR}"
  exit 1
fi

# STDOUT all the files in one line for integration test
ls ${UPLOAD_DIR} | xargs

# Cleanup upload dir
rm -rf "${UPLOAD_DIR}"
