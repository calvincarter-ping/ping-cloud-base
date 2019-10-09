#!/bin/bash

########################################################################################################################
#
# This script may be used to set up a development or test environment to verify the Kubernetes and Kustomization yaml
# files either in their present form or after making some local changes to them.
#
# ------------
# Requirements
# ------------
# The script requires the following tools to be installed:
#   - openssl
#   - base64
#   - kustomize
#   - kubectl
#   - envsubst
#
# In addition, the assumption is that kubectl is configured to authenticate and apply manifests to the Kubernetes
# cluster. For EKS clusters, this requires an AWS key and secret with the appropriate IAM policies to be configured and
# requires that the aws CLI tool and probably the aws-iam-authenticator CLI tool are installed.
#
# ------------------
# Usage instructions
# ------------------
# The script makes uses of several variables (see below) that will either come in via a couple of files:
#
#    ~/.pingidentity/devops    (Will bring in the PING_IDENTITY_DEVOPS_* variables)
#    ~/.pingidentity/aws-eks
#
# or via environment variables.  If the -s (setup) option is provided to this script, the user will be prompted for
# the TENANT_NAME, TENANT_DOMAIN, ENVIRONMENT, REGION variables and place them in the aws-eks file.
#
# These variables will be substituted into the variables in the yaml template files.
#
# Both real and dry run will emit the Kubernetes manifest file for the entire deployment into the file /tmp/deploy.yaml.
# After running the script in dry-run mode, the deploy.yaml file may be edited, if desired, but it should be able to
# be deployed as-is onto the cluster. In fact, this is exactly what gets deployed when the script is run in real
# mode, i.e. without the -n option.
#
# The following mandatory environment variables must be present before running this script.
#
# ----------------------------------------------------------------------------------------------------------------------
# Variable                    | Purpose
# ----------------------------------------------------------------------------------------------------------------------
# PING_IDENTITY_DEVOPS_USER   | A user with license to run Ping Software
# PING_IDENTITY_DEVOPS_KEY    | The key to the above user
#
# In addition, the following environment variables, if present, will be used for the following purposes:
#
# ----------------------------------------------------------------------------------------------------------------------
# Variable       | Purpose                                            | Default (if not present)
# ----------------------------------------------------------------------------------------------------------------------
# TENANT_NAME    | The name of the tenant, e.g. k8s-icecream. This    | PingPOC
#                | will be assumed to be the name of the Kubernetes   |
#                | cluster. On AWS, the cluster name is a required    |
#                | parameter to Container Insights, an AWS-specific   |
#                | logging and monitoring solution.                   |
#                |                                                    |
# TENANT_DOMAIN  | The tenant's domain, e.g. k8s-icecream.com         | eks-poc.au1.ping-lab.cloud
#                |                                                    |
# ENVIRONMENT    | An environment to isolate the Ping stack into its  | The value of the USER environment variable.
#                | own namespace within the Kubernetes cluster. This  |
#                | is useful not just in a shared multi-tenant        |
#                | Kubernetes cluster but could also be used to       |
#                | create multiple Ping stacks within the same        |
#                | cluster for testing purposes. It may be set to an  |
#                | empty string.                                      |
#                |                                                    |
# REGION         | The region where the tenant environment is         | us-east-2
#                | deployed. On AWS, this is a required parameter     |
#                | to Container Insights, an AWS-specific logging     |
#                | and monitoring solution.                           |
########################################################################################################################

# Source devops and aws-eks files, if present
test -f ~/.pingidentity/devops && . ~/.pingidentity/devops
test -f ~/.pingidentity/aws-eks && . ~/.pingidentity/aws-eks

# Source some utility methods.
. utils.sh

declare dryrun="false"

# Parse Parameters
while getopts 'ns' OPTION
do
  case ${OPTION} in
    n)
      dryrun='true'
      ;;
    s)
      setup_vars "TENANT_NAME" "TENANT_DOMAIN" "ENVIRONMENT" "REGION"
      exit 1
      ;;
    *)
      echo "Usage ${0} [ -n ] n = dry-run"
      exit 1
      ;;
  esac
done

# Checking required tools and environment variables.
HAS_REQUIRED_TOOLS=$(check_binaries "openssl" "base64" "kustomize" "kubectl" "envsubst"; echo ${?})
HAS_REQUIRED_VARS=$(check_env_vars "PING_IDENTITY_DEVOPS_USER" "PING_IDENTITY_DEVOPS_KEY"; echo ${?})

if test ${HAS_REQUIRED_TOOLS} -ne 0 || test ${HAS_REQUIRED_VARS} -ne 0; then
  exit 1
fi

# Show initial values for relevant environment variables.
echo "Initial TENANT_NAME: ${TENANT_NAME}"
echo "Initial TENANT_DOMAIN: ${TENANT_DOMAIN}"
echo "Initial ENVIRONMENT: ${ENVIRONMENT}"
echo "Initial REGION: ${REGION}"
echo ---

# A script that may be used to set up a dev/test environment against the
# current cluster. Must have the GTE devops user and key exported as
# environment variables.
export ENVIRONMENT=-"${ENVIRONMENT:-${USER}}"
export TENANT_DOMAIN="${TENANT_DOMAIN:-eks-poc.au1.ping-lab.cloud}"
export TENANT_NAME="${TENANT_NAME:-PingPOC}"
export REGION="${REGION:-us-east-2}"

ENVIRONMENT_NO_HYPHEN_PREFIX=$(echo ${ENVIRONMENT/#-})

# Show the values being used for the relevant environment variables.
echo "Using TENANT_NAME: ${TENANT_NAME}"
echo "Using TENANT_DOMAIN: ${TENANT_DOMAIN}"
echo "Using ENVIRONMENT: ${ENVIRONMENT_NO_HYPHEN_PREFIX}"
echo "Using REGION: ${REGION}"

export PING_IDENTITY_DEVOPS_USER_BASE64=$(echo -n "${PING_IDENTITY_DEVOPS_USER}" | base64)
export PING_IDENTITY_DEVOPS_KEY_BASE64=$(echo -n "${PING_IDENTITY_DEVOPS_KEY}" | base64)
export CLUSTER_NAME=${TENANT_NAME}

NAMESPACE=ping-cloud-${ENVIRONMENT_NO_HYPHEN_PREFIX}
DEPLOY_FILE=/tmp/deploy.yaml

# Generate a self-signed cert for the tenant domain.
generate_tls_cert "${TENANT_DOMAIN}"

kustomize build test |
  envsubst '${PING_IDENTITY_DEVOPS_USER_BASE64}
    ${PING_IDENTITY_DEVOPS_KEY_BASE64}
    ${ENVIRONMENT}
    ${TENANT_DOMAIN}
    ${CLUSTER_NAME}
    ${REGION}
    ${TLS_CRT_BASE64}
    ${TLS_KEY_BASE64}' > ${DEPLOY_FILE}
sed -i.bak -E "s/((namespace|name): )ping-cloud$/\1${NAMESPACE}/g" ${DEPLOY_FILE}

if test "${dryrun}" = 'false'; then
  echo "Deploying ${DEPLOY_FILE} to namespace ${NAMESPACE} for tenant ${TENANT_DOMAIN}"
  kubectl apply -f ${DEPLOY_FILE}

  # Print out the ingress objects for logs and the ping stack
  kubectl get ingress -A

  # Describe the LB service for pingdirectory
  kubectl describe svc pingdirectory-admin -n ${NAMESPACE}

  # Print out the  pods for the ping stack
  kubectl get pods -n ${NAMESPACE}
else
  less "${DEPLOY_FILE}"
fi
