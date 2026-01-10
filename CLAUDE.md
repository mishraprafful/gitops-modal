# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Modal GitOps Operator is a Kubernetes operator that enables declarative deployment of Modal serverless applications using GitOps workflows. It integrates with ArgoCD, Flux, and other GitOps tools through a `ModalDeployment` Custom Resource Definition (CRD).

## Common Commands

All commands are defined in the `Makefile`:

```bash
# Build and deploy
make build              # Build Docker image (auto-tags with git SHA)
make deploy             # Build + install operator
make install            # Install operator (requires pre-built image)
make uninstall          # Remove operator and CRD

# Development
make lint               # Run pre-commit hooks (ruff, black, yamllint, markdownlint)
make test               # Build and run tests
make test-examples      # Deploy example resources and verify they work
make load-kind          # Load Docker image into kind cluster
```

Required environment variables (set in `.env` or shell):

- `MODAL_TOKEN_ID` - Modal API token ID
- `MODAL_TOKEN_SECRET` - Modal API token secret
- `GITHUB_TOKEN` - GitHub PAT for private repos (optional)

## Architecture

The operator follows the standard Kubernetes operator pattern using Kopf:

```
ModalDeployment CRD applied → Kopf event handler (main.py)
    → ModalController (modal_controller.py)
        → Clone git repo → Extract app name → Run `modal deploy`
        → Query Modal API for app ID → Update CRD status
```

### Core Components (`operator/`)

- **`main.py`** - Kopf event handlers for CRD lifecycle (create, update, delete)
- **`modal_controller.py`** - Business logic: git cloning, app extraction, Modal CLI execution, app ID tracking
- **`health_server.py`** - HTTP health endpoints (`/healthz`, `/readyz`) on port 8081
- **`utils.py`** - Logging setup, validation helpers, condition builders

### Key Design Patterns

1. **3-Tier App ID Lookup for Deletion**: CRD status → in-memory cache → `modal app list` query
2. **Git-based Image Tagging**: Images tagged with git SHA (or `SHA-dirty` if uncommitted changes)
3. **Non-blocking Deletion**: Operator continues cleanup even if Modal API calls fail

### CRD Details

- Group: `modal.io`, Version: `v1`, Kind: `ModalDeployment`
- Short names: `md`, `modal`
- Status fields: `phase` (Deploying/Ready/Failed/Terminating), `modalAppId`, `url`, `conditions`

## Project Structure

- `operator/` - Python operator source code and Dockerfile
- `crds/` - ModalDeployment CRD definition
- `manifests/` - Kubernetes RBAC, Deployment, Secret templates
- `kustomize/` - Overlays for dev/prod environments
- `examples/` - Example ModalDeployment configurations

## Code Style

Pre-commit hooks enforce:

- Python: ruff (linting), black (formatting)
- YAML: yamllint (Kubernetes-optimized)
- Markdown: markdownlint-cli2

Run `make lint` before committing.

## Testing

- Unit tests run during Docker build (`operator/test_modal.py`)
- E2E tests deploy examples to a kind cluster (`make test-examples`)
- CI runs both lint and E2E tests on PRs to `main` and `develop`
