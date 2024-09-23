#!/bin/bash
set -e

KARPENTER_VERSION="${1}"

USAGE="./update-karpenter.sh KARPENTER_VERSION

       example: ./update-karpenter.sh  1.0.2"


helm template karpenter oci://public.ecr.aws/karpenter/karpenter --version ${KARPENTER_VERSION} --namespace kube-system \
    --set settings.aws.defaultInstanceProfile=KarpenterInstanceProfile \
    --version ${KARPENTER_VERSION} > karpenter.yaml

KARPENTER_VERSION=v${KARPENTER_VERSION}
wget https://raw.githubusercontent.com/aws/karpenter-provider-aws/${KARPENTER_VERSION}/pkg/apis/crds/karpenter.k8s.aws_ec2nodeclasses.yaml
wget https://raw.githubusercontent.com/aws/karpenter-provider-aws/${KARPENTER_VERSION}/pkg/apis/crds/karpenter.sh_nodeclaims.yaml
wget https://raw.githubusercontent.com/aws/karpenter-provider-aws/${KARPENTER_VERSION}/pkg/apis/crds/karpenter.sh_nodepools.yaml
