# ping-cloud-base

Kubernetes configuration and code generation for PingOne Advanced Services (P1AS). Contains Kustomize-based K8s manifests, CI/CD pipelines, and templating tools for deploying PingFederate, PingDirectory, PingAccess, and related products on AWS EKS.

## Directory Structure

- `k8s-configs/` — Kustomize manifests: `base/` (shared), `prod/` (sized overlays: x-small/small/medium/large), `test/` (per-product test overlays), `cluster-tools/`
- `code-gen/` — Cluster state generation scripts and product templates
- `tests/` — Per-product bash test suites (numbered scripts, e.g. `tests/pingfederate/02-test-heartbeat-ping.sh`)
- `build/` — Image mapping and release utilities
- `docs/` — Documentation

## Key Scripts

- `code-gen/generate-cluster-state.sh` — Main entry point; generates K8s manifests from templates and properties
- `code-gen/push-cluster-state.sh` — Structures generated manifests into cluster-state-repo format (destructive; use `DISABLE_GIT=true` for local testing)
- `code-gen/csr-validation.sh` — Validates cluster-state-repo structure
- `utils.sh` — Shared utility functions (logging, error handling)
- `pingcloud-scripts.sh` — P1AS-specific helper functions

## Tests

Tests are bash scripts in `tests/{product}/` run by the GitLab CI pipeline. There is no local test runner — tests execute inside the `K8S_DEPLOY_TOOLS` CI container against a live cluster.

To understand a test: each script sources `/ci-scripts/common.sh`, defines an optional `oneTimeSetUp()`, and uses `skipTest` for conditional skips.

CI stages: compile → find-cluster → deploy → integration-test → chaos → cleanup → security → merge-branch (defined in `.gitlab-ci.yml`).

## Conventions

- Shell scripts use `#!/bin/bash`; Python scripts use `#!/usr/bin/env python3`
- `set -e` enforced; `VERBOSE=true` and `EXIT_ON_FAILURE` env vars available in code-gen scripts
- Test scripts are numbered for execution order (`01-`, `02-`, etc.)
- Directory names match container/product names (`pingaccess`, `pingfederate`, etc.)
- Kustomize is used for all K8s manifest composition; Helm charts referenced via Flux/ArgoCD
