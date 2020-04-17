#!/usr/bin/env sh

########################################################################################################################
# Makes curl request to PingFederate Admin API to configure.
#
# Arguments
#   $@ -> The URL and additional needed data to make request
########################################################################################################################
function make_api_request()
{
    set +x
    curl -k --retry ${API_RETRY_LIMIT} --max-time ${API_TIMEOUT_WAIT} --retry-delay 1 --retry-connrefuse \
        -u Administrator:${PF_LDAP_PASSWORD} -H "X-Xsrf-Header: PingFederate " "$@"
    if test ! $? -eq 0; then
        echo "Admin API connection refused"
        exit 1
    fi
    set -x
}

########################################################################################################################
# Wait for the local PingFederate admin server to be up and running waiting 3 seconds between each check.
########################################################################################################################
function wait_for_server_ready() {
  while true; do
    liveness.sh && return 0
    sleep 3s
  done
}

########################################################################################################################
# Function to install AWS command line tools
#
# Arguments
#   N/A
########################################################################################################################
function installTools()
{
   if [ -z "$(which aws)" ]; then
      #   
      #  Install AWS platform specific tools
      #
      echo "Installing AWS CLI tools for S3 support"
      #
      # TODO: apk needs to move to the Docker file as the package manager is plaform specific
      #
      apk --update add python3
      pip3 install --no-cache-dir --upgrade pip
      pip3 install --no-cache-dir --upgrade awscli
   fi
}

#---------------------------------------------------------------------------------------------
# Function to obfuscate LDAP password
#---------------------------------------------------------------------------------------------

function obfuscatePassword()
{
   #
   # Ensure Java home is set
   #
   if [ -z "${JAVA_HOME}" ]; then
      export JAVA_HOME=/usr/lib/jvm/default-jvm/jre/
   fi
   #
   # The master key may not exist, this means no key was passed in as a secret and this is the first run of PF
   # for this environment, we can use the obfuscate utility to generate a master key as a byproduct of obfuscating
   # the password used to authenticate to PingDirectory in the ldap properties file.
   #
   # Obfuscate the ldap password
   #
   export PF_LDAP_PASSWORD_OBFUSCATED=$(sh ./obfuscate.sh  ${PF_LDAP_PASSWORD}| tr -d '\n')
   #
   # Inject obfuscated password into ldap properties file. The password variable is protected with a ${_DOLLAR_}
   # prefix because the file is substituted twice the first pass sets the DN and resets the '$' on the password
   # variable so it's a legitimate candidate for substitution on this, the second pass.
   #
   mv ldap.properties ldap.properties.subst
   envsubst < ldap.properties.subst > ldap.properties
   rm ldap.properties.subst
   PF_LDAP_PASSWORD_OBFUSCATED="${PF_LDAP_PASSWORD_OBFUSCATED:8}"
   mv ../server/default/data/pingfederate-ldap-ds.xml ../server/default/data/pingfederate-ldap-ds.xml.subst
   envsubst < ../server/default/data/pingfederate-ldap-ds.xml.subst > ../server/default/data/pingfederate-ldap-ds.xml
   rm ../server/default/data/pingfederate-ldap-ds.xml.subst
}

########################################################################################################################
# Function calls installTools() and sets required environment variables for AWS S3 bucket
#
########################################################################################################################
function initializeS3Configuration() {
  unset BUCKET_URL_NO_PROTOCOL
  unset BUCKET_NAME
  unset DIRECTORY_NAME
  unset TARGET_URL

  # Allow overriding the backup URL with an arg
  test ! -z "${1}" && BACKUP_URL="${1}"

  # Install AWS CLI if the upload location is S3
  if test "${BACKUP_URL#s3}" == "${BACKUP_URL}"; then
    echo "Upload location is not S3"
    exit 1
  else
    installTools
  fi

  export BUCKET_URL_NO_PROTOCOL=${BACKUP_URL#s3://}
  export BUCKET_NAME=$(echo "${BUCKET_URL_NO_PROTOCOL}" | cut -d/ -f1)
  export DIRECTORY_NAME=$(echo "${PING_PRODUCT}" | tr '[:upper:]' '[:lower:]')

  if test "${BACKUP_URL}" == */"${DIRECTORY_NAME}"; then
    export TARGET_URL="${BACKUP_URL}"
  else
    export TARGET_URL="${BACKUP_URL}/${DIRECTORY_NAME}"
  fi
}

