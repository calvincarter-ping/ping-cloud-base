#!/bin/bash -e

########################################################################################################################
# Prints script usage
########################################################################################################################
usage() {
  echo "Usage: ${0} SOURCE_REF TARGET_REF [REF_TYPE]"
  echo "  where"
  echo "    SOURCE_REF => source ref from where to create the target ref, e.g. master"
  echo "    TARGET_REF => the target ref, e.g. v1.0.0"
  echo "    REF_TYPE => the target ref type - tag or branch, default is tag"
}

########################################################################################################################
# Replaces the current version references in the source ref with the target ref in all the necessary places. Then,
# commits the changes into the target ref(branch or tag). Must be in the ping-cloud-base directory for it to work
# correctly.
#
# Arguments:
#   ${1} -> The source ref
#   ${2} -> The target ref
#   ${3} -> The ref type- tag
########################################################################################################################
replaceAndCommit() {
  SOURCE=${1}
  TARGET=${2}
  REF_TYPE=${3}

  echo "Changing ${SOURCE} -> ${TARGET} in expected files"

  git grep -l "^SERVER_PROFILE_BRANCH=${SOURCE}" | xargs sed -i.bak "s/^\(SERVER_PROFILE_BRANCH=\)${SOURCE}$/\1${TARGET}/g"

  #update base env vars

  grep_var "PINGACCESS_IMAGE_TAG" "${SOURCE}" "${TARGET}"
  grep_var "PINGACCESS_WAS_IMAGE_TAG" "${SOURCE}" "${TARGET}"
  grep_var "PINGFEDERATE_IMAGE_TAG" "${SOURCE}" "${TARGET}"
  grep_var "PINGDIRECTORY_IMAGE_TAG" "${SOURCE}" "${TARGET}"
  grep_var "PINGDELEGATOR_IMAGE_TAG" "${SOURCE}" "${TARGET}"
  grep_var "PINGCENTRAL_IMAGE_TAG" "${SOURCE}" "${TARGET}"
  grep_var "PINGDATASYNC_IMAGE_TAG" "${SOURCE}" "${TARGET}"
  grep_var "METADATA_IMAGE_TAG" "${SOURCE}" "${TARGET}"
  grep_var "P14C_BOOTSTRAP_IMAGE_TAG" "${SOURCE}" "${TARGET}"
  grep_var "P14C_INTEGRATION_IMAGE_TAG" "${SOURCE}" "${TARGET}"
  grep_var "ANSIBLE_BELUGA_IMAGE_TAG" "${SOURCE}" "${TARGET}"

  #update k8s yaml files

  grep_yaml "pingaccess" "pingcloud-apps" "${SOURCE}" "${TARGET}"
  grep_yaml "pingaccess-was" "pingcloud-apps" "${SOURCE}" "${TARGET}"
  grep_yaml "pingfederate" "pingcloud-apps" "${SOURCE}" "${TARGET}"
  grep_yaml "pingdirectory" "pingcloud-apps" "${SOURCE}" "${TARGET}"
  grep_yaml "pingdelegator" "pingcloud-apps" "${SOURCE}" "${TARGET}"
  grep_yaml "pingcentral" "pingcloud-apps" "${SOURCE}" "${TARGET}"
  grep_yaml "pingdatasync" "pingcloud-apps" "${SOURCE}" "${TARGET}"
  grep_yaml "metadata" "pingcloud-services" "${SOURCE}" "${TARGET}"
  grep_yaml "p14c-bootstrap" "pingcloud-services" "${SOURCE}" "${TARGET}"
  grep_yaml "p14c-integration" "pingcloud-services" "${SOURCE}" "${TARGET}"
  grep_yaml "ansible-beluga" "pingcloud-solutions" "${SOURCE}" "${TARGET}"

  echo "Committing changes for new ${REF_TYPE} ${TARGET}"
  git add .
  git commit -m "[skip pipeline] - creating new ${REF_TYPE} ${TARGET}"
}

grep_var() {

  local VAR=${1}
  local SOURCE_VALUE=${2}
  local TARGET_VALUE=${3}

  verify_var=$(git grep -l "^${VAR}=${SOURCE_VALUE}" | wc -l)
  if test ${verify_var} = 0; then
    usage
    exit 1
  else
    echo "Changing ${SOURCE_VALUE} -> ${TARGET_VALUE} in expected files"
    git grep -l "^${VAR}=${SOURCE_VALUE}" | xargs sed -i.bak "s/^\(${VAR}=\)${SOURCE_VALUE}$/\1${TARGET_VALUE}/g"
  fi

}

grep_yaml() {

  local VAR=${1}
  local ECR_REPO=${2}
  local SOURCE_VALUE=${3}
  local TARGET_VALUE=${4}

  local image="image: public.ecr.aws/r2h3l6e4/${2}/${1}"

  cd "${SANDBOX}"/ping-cloud-base/k8s-configs

  verify_yaml=$(git grep -l "${image}:${SOURCE_VALUE}" | wc -l)
  if [[ ${verify_yaml} == 0 ]]; then
    usage
    exit 1
  else
    echo "Changing ${image}:${SOURCE_VALUE} -> ${image}:${TARGET_VALUE} in expected files"
    git grep -l "${image}:${SOURCE_VALUE}" | xargs sed -i.bak "s/${SOURCE_VALUE}/${TARGET_VALUE}/g"
  fi

  cd "${SANDBOX}"/ping-cloud-base/

}

verify_ref_name() {

  local value=${1}

  # TODO: Change to 'release-branch'
  REGEX='^v[0-9]+.[0-9]+-new-image-process$'

  # REGEX='^pdo-[0-9]+$'

  if [[ $value =~ $REGEX ]]; then
    echo "$value is a release branch"
    export REF_NAME="release-branch"
  else
    echo "$value is  RC"
    export REF_NAME="rc"
  fi
}

SOURCE_REF=${1}
TARGET_REF=${2}
REF_TYPE=${3}

if test -z "${SOURCE_REF}" || test -z "${TARGET_REF}"; then
  usage
  exit 1
fi

SCRIPT_DIR=$(dirname "${0}")
pushd "${SCRIPT_DIR}" &>/dev/null

SANDBOX=$(mktemp -d)
echo "Making modifications in sandbox directory ${SANDBOX}"

cd "${SANDBOX}"
git clone git@gitlab.corp.pingidentity.com:ping-cloud-private-tenant/ping-cloud-base.git

echo ---
cd ping-cloud-base
git checkout "${SOURCE_REF}"

###########################################################################################################################
# Verifies the 'REF_TYPE' if its a 'tag' or 'branch'.
#
# (1) -->if the target value is to be replaced by a 'tag' , 'verify_ref_name' method helps validate the source value if its
#  a "release-branch(v*.*-release-branch)" or a "tag (RC)".
#
#
# This would be applicable in phases "Ready to Release" and also during "Hardening" wherein the env_vars and other values
# need to be replaced from 'v*.*-release-branch-latest' to 'RC tag' [or] if there is a new 'RC tag' that needs to be updated.
# 
#
#
# (2) -->if the target value is to be replaced by a 'branch' , 'verify_ref_name' method simply helps validate the target
# value if its a "release-branch(v*.*-release-branch)" or not and breaks if any other value is provided.
#
#
###########################################################################################################################
if test "${REF_TYPE}" = 'tag'; then
  verify_ref_name "${SOURCE_REF}"
  if test "${REF_NAME}" = 'release-branch'; then
    replaceAndCommit "${SOURCE_REF}-latest" "${TARGET_REF}" "${REF_TYPE}"
  elif test "${REF_NAME}" = 'rc'; then
    replaceAndCommit "${SOURCE_REF}" "${TARGET_REF}" "${REF_TYPE}"
  else
    usage
    exit 1
  fi
  git tag "${TARGET_REF}"
  unset REF_NAME

else
  verify_ref_name "${TARGET_REF}"
  if test "${REF_NAME}" = 'release-branch'; then
    git checkout -b "${TARGET_REF}"
    replaceAndCommit "${SOURCE_REF}" "${TARGET_REF}-latest"
  else
    usage
    exit 1
  fi
  unset REF_NAME
fi

echo ---
echo "Files that are different between origin/${SOURCE_REF} and ${TARGET_REF} refs:"
git diff --name-only origin/"${SOURCE_REF}" "${TARGET_REF}"

echo ---

# Confirm before pushing the tag to the server
read -n 1 -srp 'Press any key to continue'
git push origin "${TARGET_REF}"

popd &>/dev/null

#todo- update "usage" method
