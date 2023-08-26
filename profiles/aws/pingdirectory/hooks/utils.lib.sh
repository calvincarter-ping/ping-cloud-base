#!/usr/bin/env sh

. "${HOOKS_DIR}/logger.lib.sh"

# Check and source environment variable(s) generated by discovery service
test -f "${STAGING_DIR}/ds_env_vars" && . "${STAGING_DIR}/ds_env_vars"

#########################################################################################################################
# Function sets required environment variables for backup
#
########################################################################################################################
function initializeS3Configuration() {
  unset   BACKUP_CLOUD_PREFIX

  # Allow overriding the backup URL with an arg
  test ! -z "${1}" && BACKUP_URL="${1}"

  # Check if endpoint is AWS cloud storage service (S3 bucket)
  case "$BACKUP_URL" in "s3://"*)

    # Set AWS specific variable for backup
    export AWS_REGION=${REGION}

    DIRECTORY_NAME=$(echo "${PING_PRODUCT}" | tr '[:upper:]' '[:lower:]')

    if ! $(echo "$BACKUP_URL" | grep -q "/$DIRECTORY_NAME"); then
      BACKUP_URL="${BACKUP_URL}/${DIRECTORY_NAME}"
    fi

  esac

  export BACKUP_CLOUD_PREFIX="${BACKUP_URL}"
}

########################################################################################################################
# Function to copy file(s) between cloud storage and k8s
#
# Arguments
#   $1 -> desired source to copy from.
#   $2 -> desired destination to copy to.
#   s3 -> use recursion flag. will use recursion if any value is passed. if set will target all files in directory
########################################################################################################################
function awscliCopy() {
  SOURCE="${1}"
  DESTINATION="${2}"
  RECURSIVE="${3}"

  if [ -n "$RECURSIVE" ]; then
    if ! aws s3 cp "$SOURCE" "${DESTINATION}" --recursive; then
      return 1
    fi
  else
    if ! aws s3 cp "$SOURCE" "${DESTINATION}"; then
      return 1
    fi
  fi
}

########################################################################################################################
# Export values for PingDirectory configuration settings based on single vs. multi cluster.
########################################################################################################################
function export_config_settings() {
  export SHORT_HOST_NAME=$(hostname)
  export ORDINAL=${SHORT_HOST_NAME##*-}
  export LOCAL_DOMAIN_NAME="$(hostname -f | cut -d'.' -f2-)"

  # For multi-region:
  # If using NLB to route traffic between the regions, the hostnames will be the same per region (i.e. that of the NLB),
  # but the ports will be different. If using VPC peering (i.e. creating a super network of the subnets) for routing
  # traffic between the regions, then each PD server will be directly addressable, and so will have a unique hostname
  # and may use the same port.

  # NOTE: If using NLB, then corresponding changes will be required to the 80-post-start.sh.test script to export port 6360,
  # 6361, etc. on each server in a region. Since we have VPC peering in Ping Cloud, all servers can use the same LDAPS
  # port, i.e. 1636, so we don't expose 636${ORDINAL} anymore.

  if is_multi_cluster; then
    export MULTI_CLUSTER=true
    is_primary_cluster &&
      export PRIMARY_CLUSTER=true ||
      export PRIMARY_CLUSTER=false

    # NLB settings:
    # export PD_HTTPS_PORT="443"
    # export PD_LDAP_PORT="389${ORDINAL}"
    # export PD_LDAPS_PORT="636${ORDINAL}"
    # export PD_REPL_PORT="989${ORDINAL}"

    # VPC peer settings (same as single-region case):
    export PD_HTTPS_PORT="${HTTPS_PORT}"
    export PD_LDAP_PORT="${LDAP_PORT}"
    export PD_LDAPS_PORT="${LDAPS_PORT}"
    export PD_REPL_PORT="${REPLICATION_PORT}"

    export PD_CLUSTER_DOMAIN_NAME="${PD_CLUSTER_PUBLIC_HOSTNAME}"
  else
    export MULTI_CLUSTER=false
    export PRIMARY_CLUSTER=true

    export PD_HTTPS_PORT="${HTTPS_PORT}"
    export PD_LDAP_PORT="${LDAP_PORT}"
    export PD_LDAPS_PORT="${LDAPS_PORT}"
    export PD_REPL_PORT="${REPLICATION_PORT}"

    export PD_CLUSTER_DOMAIN_NAME="${LOCAL_DOMAIN_NAME}"
  fi

  export PD_SEED_LDAP_HOST="${K8S_STATEFUL_SET_NAME}-0.${PD_CLUSTER_DOMAIN_NAME}"
  export LOCAL_HOST_NAME="${K8S_STATEFUL_SET_NAME}-${ORDINAL}.${PD_CLUSTER_DOMAIN_NAME}"
  export LOCAL_INSTANCE_NAME="${K8S_STATEFUL_SET_NAME}-${ORDINAL}-${REGION_NICK_NAME}"

  # Figure out the list of DNs to initialize replication on
  DN_LIST=
  if test -z "${REPLICATION_BASE_DNS}"; then
    DN_LIST="${USER_BASE_DN}"
  else
    echo "${REPLICATION_BASE_DNS}" | grep -q "${USER_BASE_DN}"
    test $? -eq 0 &&
        DN_LIST="${REPLICATION_BASE_DNS}" ||
        DN_LIST="${REPLICATION_BASE_DNS};${USER_BASE_DN}"
  fi

  export DNS_TO_ENABLE=$(echo "${DN_LIST}" | tr ';' ' ')
  export REPL_INIT_MARKER_FILE="${SERVER_ROOT_DIR}"/config/repl-initialized
  export POST_START_INIT_MARKER_FILE="${SERVER_ROOT_DIR}"/config/post-start-init-complete

  export UNINITIALIZED_DNS=
  for DN in ${DNS_TO_ENABLE}; do
    if ! grep -q "${DN}" "${REPL_INIT_MARKER_FILE}" &> /dev/null; then
      test -z "${UNINITIALIZED_DNS}" &&
          export UNINITIALIZED_DNS="${DN}" ||
          export UNINITIALIZED_DNS="${UNINITIALIZED_DNS} ${DN}"
    fi
  done

  beluga_log "MULTI_CLUSTER - ${MULTI_CLUSTER}"
  beluga_log "PRIMARY_CLUSTER - ${PRIMARY_CLUSTER}"
  beluga_log "PD_HTTPS_PORT - ${PD_HTTPS_PORT}"
  beluga_log "PD_LDAP_PORT - ${PD_LDAP_PORT}"
  beluga_log "PD_LDAPS_PORT - ${PD_LDAPS_PORT}"
  beluga_log "PD_REPL_PORT - ${PD_REPL_PORT}"
  beluga_log "PD_CLUSTER_DOMAIN_NAME - ${PD_CLUSTER_DOMAIN_NAME}"
  beluga_log "PD_SEED_LDAP_HOST - ${PD_SEED_LDAP_HOST}"
  beluga_log "LOCAL_HOST_NAME - ${LOCAL_HOST_NAME}"
  beluga_log "LOCAL_INSTANCE_NAME - ${LOCAL_INSTANCE_NAME}"
  beluga_log "DNS_TO_ENABLE - ${DNS_TO_ENABLE}"
  beluga_log "UNINITIALIZED_DNS - ${UNINITIALIZED_DNS}"
}

########################################################################################################################
# Determines if the environment is running in the context of multiple clusters.
#
# Returns
#   true if multi-cluster; false if not.
########################################################################################################################
function is_multi_cluster() {
  test ! -z "${IS_MULTI_CLUSTER}" && "${IS_MULTI_CLUSTER}"
}

########################################################################################################################
# Determines if the environment is set up in the primary cluster.
#
# Returns
#   true if primary cluster; false if not.
########################################################################################################################
function is_primary_cluster() {
  test "${TENANT_DOMAIN}" = "${PRIMARY_TENANT_DOMAIN}"
}

########################################################################################################################
# Determines if the environment is set up in a secondary cluster.
#
# Returns
#   true if secondary cluster; false if not.
########################################################################################################################
function is_secondary_cluster() {
  ! is_primary_cluster
}

########################################################################################################################
# Get LDIF for the base entry of USER_BASE_DN and return the LDIF file as stdout
########################################################################################################################
get_base_entry_ldif() {
  COMPUTED_DOMAIN=$(echo "${USER_BASE_DN}" | sed 's/^dc=\([^,]*\).*/\1/')
  COMPUTED_ORG=$(echo "${USER_BASE_DN}" | sed 's/^o=\([^,]*\).*/\1/')

  USER_BASE_ENTRY_LDIF=$(mktemp)

  if ! test "${USER_BASE_DN}" = "${COMPUTED_DOMAIN}"; then
    cat > "${USER_BASE_ENTRY_LDIF}" <<EOF
dn: ${USER_BASE_DN}
objectClass: top
objectClass: domain
dc: ${COMPUTED_DOMAIN}
EOF
  elif ! test "${USER_BASE_DN}" = "${COMPUTED_ORG}"; then
    cat > "${USER_BASE_ENTRY_LDIF}" <<EOF
dn: ${USER_BASE_DN}
objectClass: top
objectClass: organization
o: ${COMPUTED_ORG}
EOF
  else
    beluga_error "User base DN must be either 1 or 2-level deep, for example: dc=foobar,dc=com or o=data"
    return 80
  fi

  # Append some required ACIs to the base entry file. Without these, PF SSO will not work.
  cat >> "${USER_BASE_ENTRY_LDIF}" <<EOF
aci: (targetattr!="userPassword")(version 3.0; acl "Allow read access for all"; allow (read,search,compare) userdn="ldap:///all";)
aci: (targetattr!="userPassword")(version 3.0; acl "Allow self-read access to all user attributes except the password"; allow (read,search,compare) userdn="ldap:///self";)
aci: (targetattr="*")(version 3.0; acl "Allow users to update their own entries"; allow (write) userdn="ldap:///self";)
aci: (targetattr="*")(version 3.0; acl "Grant full access for the admin user"; allow (all) userdn="ldap:///uid=admin,${USER_BASE_DN}";)
EOF

  echo "${USER_BASE_ENTRY_LDIF}"
}


get_base_entry_ldif_generation_id() {
  COMPUTED_DOMAIN=$(echo "${USER_BASE_DN}" | sed 's/^dc=\([^,]*\).*/\1/')
  COMPUTED_ORG=$(echo "${USER_BASE_DN}" | sed 's/^o=\([^,]*\).*/\1/')

  USER_BASE_ENTRY_LDIF=$(mktemp)

  if ! test "${USER_BASE_DN}" = "${COMPUTED_DOMAIN}"; then
    cat > "${USER_BASE_ENTRY_LDIF}" <<EOF
dn: ${USER_BASE_DN}
objectClass: top
objectClass: domain
dc: ${COMPUTED_DOMAIN}
ds-sync-generation-id: -1
EOF
  elif ! test "${USER_BASE_DN}" = "${COMPUTED_ORG}"; then
    cat > "${USER_BASE_ENTRY_LDIF}" <<EOF
dn: ${USER_BASE_DN}
objectClass: top
objectClass: organization
o: ${COMPUTED_ORG}
ds-sync-generation-id: -1
EOF
  else
    beluga_error "User base DN must be either 1 or 2-level deep, for example: dc=foobar,dc=com or o=data"
    return 80
  fi

  # Append some required ACIs to the base entry file. Without these, PF SSO will not work.
  cat >> "${USER_BASE_ENTRY_LDIF}" <<EOF
aci: (targetattr!="userPassword")(version 3.0; acl "Allow read access for all"; allow (read,search,compare) userdn="ldap:///all";)
aci: (targetattr!="userPassword")(version 3.0; acl "Allow self-read access to all user attributes except the password"; allow (read,search,compare) userdn="ldap:///self";)
aci: (targetattr="*")(version 3.0; acl "Allow users to update their own entries"; allow (write) userdn="ldap:///self";)
aci: (targetattr="*")(version 3.0; acl "Grant full access for the admin user"; allow (all) userdn="ldap:///uid=admin,${USER_BASE_DN}";)
EOF

  echo "${USER_BASE_ENTRY_LDIF}"
}

########################################################################################################################
# Add the base entry of USER_BASE_DN if it needs to be added
########################################################################################################################
add_base_entry_if_needed() {
  num_user_entries=$(dbtest list-entry-containers --backendID "${USER_BACKEND_ID}" 2>/dev/null |
    grep -i "${USER_BASE_DN}" | awk '{ print $4; }')
  beluga_log "Number of sub entries of DN ${USER_BASE_DN} in ${USER_BACKEND_ID} backend: ${num_user_entries}"

  if test "${num_user_entries}" && test "${num_user_entries}" -gt 0; then
    beluga_log "Replication base DN ${USER_BASE_DN} already added"
    return 0
  else

    # Replicated base DNs must exist before starting the server now that
    # replication is enabled before start. Otherwise a generation ID of -1
    # would be generated, which breaks replication.
    base_entry_ldif=$(get_base_entry_ldif)
    get_entry_status=$?
    beluga_log "get user base entry status: ${get_entry_status}"
    test ${get_entry_status} -ne 0 && return ${get_entry_status}

    beluga_log "Adding replication base DN ${USER_BASE_DN} with contents:"
    cat "${base_entry_ldif}"

    import-ldif -n "${USER_BACKEND_ID}" -l "${base_entry_ldif}" \
        --includeBranch "${USER_BASE_DN}" --overwriteExistingEntries
    import_status=$?
    beluga_log "import user base entry status: ${import_status}"
    return ${import_status}
  fi
}

########################################################################################################################
# Post notification to argo-events webhook.
########################################################################################################################
notify() {
  MESSAGE=${1}
  STATUS=${2:-ERROR}
  NOTIFICATION_ENABLED=${NOTIFICATION_ENABLED:-false}
  BODY="{'STATUS': '${STATUS}', 'TENANT_DOMAIN':'${TENANT_DOMAIN}', 'ENVIRONMENT_TYPE':'${ENVIRONMENT_TYPE}', 'MSG':'${MESSAGE}', 'APP':'${HOSTNAME}'}"
  
  # Cleanup quotes
  NOTIFICATION_ENABLED=$(echo ${NOTIFICATION_ENABLED} | tr -d '"' | tr -d "'")

  if test "${NOTIFICATION_ENABLED}" == "true"; then
    curl -d '{"channel":"'"${SLACK_CHANNEL}"'","message": "'"${BODY}"'" }' \
         -H "Content-Type: application/json" -X POST ${NOTIFICATION_ENDPOINT}
  fi
}

########################################################################################################################
# Enable the replication sub-system in offline mode.
########################################################################################################################
offline_enable_replication() {
  # Enable replication offline.
  "${HOOKS_DIR}"/185-offline-enable-wrapper.sh
  enable_status=$?
  beluga_log "offline replication enable status: ${enable_status}"
  test ${enable_status} -ne 0 && return ${enable_status}

  return 0
}

########################################################################################################################
# Get backend corresponding DN.
# Returns
#   DN of backend_id.
########################################################################################################################
get_base_dn_using_backend_id() {
  # Build a map/dictionary by storing backend_id as keys and its value as its corresponding DN.

  # To create map/dictionary use the eval command to set the backend_id real value as variables
  # This will be called, _backend_id_key, variable.
  # The _backend_id_key will be equal to its corresponding DN
  #
  # e.g.
  #      => _backend_id_key real value 'appintegrations' will be set as DN value 'o=appintegrations'
  #      => _backend_id_key real value 'platformconfig'  will be set as DN value 'o=platformconfig'
  #      => _backend_id_key real value 'userRoot'        will be set as DN value 'dc=example,dc=com'
  #
  # So in summary bourne-shell will create following variables in memory:
  # local appintegrations=o=appintegrations
  # local platformconfig=o=platformconfig
  # local userRoot=dc=example,dc=com
  eval local $(echo "${PLATFORM_CONFIG_BACKEND_ID}"=)"${PLATFORM_CONFIG_BASE_DN}"
  eval local $(echo "${APP_INTEGRATIONS_BACKEND_ID}"=)"${APP_INTEGRATIONS_BASE_DN}"
  eval local $(echo "${USER_BACKEND_ID}"=)"${USER_BASE_DN}"

  _backend_id_key="${1}"

  # Using eval echo commands, return DN
  # e.g.
  # echo ${appintegrations} will return o=appintegrations
  # echo ${platformconfig} will return o=platformconfig
  # echo ${userRoot} will return dc=example,dc=com
  eval echo \$"${_backend_id_key}"
}

########################################################################################################################
# Attempt to rebuild index of base DN for all backends.
########################################################################################################################
rebuild_base_dn_indexes() {

  # Easily access all global variables of backend_ids for PingDirectory
  all_backend_ids="${PLATFORM_CONFIG_BACKEND_ID} \
    ${APP_INTEGRATIONS_BACKEND_ID} \
    ${USER_BACKEND_ID}"

  ERROR_MSG=

  # Iterate over all backends and get its corresponding DN
  for backend_key in ${all_backend_ids}; do
    dn_value=$(get_base_dn_using_backend_id "${backend_key}")
    beluga_log "Checking if backend_id: ${backend_key}, dn: ${dn_value} needs its indexes rebuilt"

    # Rebuild indexes, if necessary for DN.
    if dbtest list-database-containers --backendID "${backend_key}" 2> /dev/null | grep -E '(NEW|UNTRUSTED)'; then
      beluga_log "Rebuilding any new or untrusted indexes for base DN ${dn_value}"
      rebuild-index --bulkRebuild new --bulkRebuild untrusted --baseDN "${dn_value}" 2>> /tmp/rebuild-index.out
      rebuild_index_status=$?

      if test ${rebuild_index_status} -ne 0; then
        ERROR_MSG="${ERROR_MSG} backend_id:${backend_key} with dn:${dn_value} \
          failed during rebuild index: ${rebuild_index_status}"
      fi
    else
      beluga_log "Not rebuilding indexes for backend_id:'${backend_key}' dn:'${dn_value}' as there are no indexes to rebuild with status NEW or UNTRUSTED"
    fi
  done

  if [ -n "${ERROR_MSG}" ]; then
    beluga_error "The following backend and DN failed when attempting to build its indexes"
    beluga_error "${ERROR_MSG}"
    cat /tmp/rebuild-index.out
    return 1
  fi

  return 0
}

# TODO: remove once BRASS fixes export_container_env in:
#   docker-builds/pingcommon/opt/staging/hooks/pingcommon.lib.sh
# CUSTOM Beluga version of export_container_env - overrides the BRASS version to
# add single quotes around the env var value to support spaces in the value,
# but without any unexpected interpolation (e.g. JAVA_OPTS='-D1 -D2')
b_export_container_env() {
  {
    echo ""
    echo "# Following variables set by hook ${CALLING_HOOK}"
  } >> "${CONTAINER_ENV}"

  while test -n "${1}"; do
    _var=${1} && shift
    _val=$(get_value "${_var}")

    # Modified portion - add single quotes
    echo "${_var}='${_val}'" >> "${CONTAINER_ENV}"
  done
}

# Decrypts the file passed in as $1 to $1.decrypted, if it isn't already decrypted
decrypt_file() {
  FILE_TO_DECRYPT=$1
  if test ! -f "${FILE_TO_DECRYPT}.decrypted"; then
    encrypt-file --decrypt \
      --input-file "${FILE_TO_DECRYPT}" \
      --output-file "${FILE_TO_DECRYPT}.decrypted" ||
      (beluga_warn "Error decrypting" && exit 0)
  fi
}

function get_other_running_pingdirectory_pods() {
  local running_pingdirectory_pods=$(kubectl get pods \
    -l class=pingdirectory-server \
    -o=jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.containerStatuses[*].ready}{"\n"}{end}' |\
      awk '$2=="true"{print $1}')

  local selected_pingdirectory_pod=""
  for current_pingdirectory_pod in ${running_pingdirectory_pods}; do
    if test "${SHORT_HOST_NAME}" = "${current_pingdirectory_pod}"; then
      continue
    fi
    selected_pingdirectory_pod="${current_pingdirectory_pod}\n"
  done

  echo -e "${selected_pingdirectory_pod}"
}

function is_genesis_server() {
  if test "${RUN_PLAN}" != "START"; then
    return 1
  fi

  local all_running_pingdirectory_pods=$(kubectl get pods \
      -l class=pingdirectory-server \
      -o=jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.containerStatuses[*].ready}{"\n"}{end}' |\
        awk '$2=="true"{print $1}')
  num_of_running_pods=$(all_running_pingdirectory_pods | wc -l)
  test ${num_of_running_pods} -eq 0
}

function find_replicated_host_server() {
  get_other_running_pingdirectory_pods | head -n 1
}

# These are needed by every script - so export them when this script is sourced.
beluga_log "export config settings"
export_config_settings