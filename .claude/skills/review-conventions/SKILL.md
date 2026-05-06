---
name: review-conventions
description: Code review guidelines for ping-cloud-base
---

## What to check

**Shell scripts**
- Scripts must start with `#!/bin/bash`
- Production scripts must use `set -e` (fail fast on errors)
- Avoid silent failures — errors should be logged or propagated
- Use the utility functions in `utils.sh` rather than reimplementing logging/error handling

**Kubernetes / Kustomize**
- Changes to `k8s-configs/base/` affect all environments — flag any change here for extra scrutiny
- Size-specific overlays live in `k8s-configs/prod/{x-small,small,medium,large}/` — check that changes are applied consistently across sizes when intended
- Prefer Kustomize patches over duplicating full resource specs

**Code generation**
- Changes to `code-gen/generate-cluster-state.sh` or templates affect all new customer deployments — treat as high-impact
- `code-gen/push-cluster-state.sh` is destructive by design; changes need careful review

**Tests**
- New product functionality should have a corresponding test in `tests/{product}/`
- Tests should follow the numbered script pattern and source `/ci-scripts/common.sh`
- Tests run only in CI against a live cluster — there is no local test runner

## General
- This is an infrastructure repo — configuration mistakes can affect production customer environments
- When in doubt about blast radius, flag it explicitly in the review
