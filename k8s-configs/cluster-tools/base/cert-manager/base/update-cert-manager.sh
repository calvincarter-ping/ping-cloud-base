#!/bin/bash
set -e

CERT_MANAGER_VERSION="${1}"

USAGE="./update-cert-manager.sh CERT_MANAGER_VERSION

       example: ./update-cert-manager.sh v1.16.1"


if [[ $# -ne 1 ]]; then
    echo "Invalid number of arguments"
    echo "${USAGE}"
    exit 1
fi

wget https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml -O cert-manager.yaml

#wget https://raw.githubusercontent.com/aws/karpenter-provider-aws/${KARPENTER_VERSION}/pkg/apis/crds/karpenter.k8s.aws_ec2nodeclasses.yaml
#wget https://raw.githubusercontent.com/aws/karpenter-provider-aws/${KARPENTER_VERSION}/pkg/apis/crds/karpenter.sh_nodeclaims.yaml
#wget https://raw.githubusercontent.com/aws/karpenter-provider-aws/${KARPENTER_VERSION}/pkg/apis/crds/karpenter.sh_nodepools.yaml
