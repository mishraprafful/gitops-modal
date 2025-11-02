# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-11-02

### Added

#### Core Operator Features

- Kubernetes operator for managing Modal deployments via Custom Resource Definitions (CRDs)
- `ModalDeployment` CRD (`modal.io/v1`) for declarative Modal app deployments
- Automatic reconciliation loop that watches for CREATE, UPDATE, and DELETE events
- Status tracking with phase indicators (`Pending`, `Deploying`, `Ready`, `Failed`, `Terminating`)
- Health endpoints (`/healthz` for liveness, `/readyz` for readiness) on port 8081

#### Git Integration

- Clone Modal applications directly from Git repositories
- Support for public Git repositories (HTTPS)
- Support for private Git repositories via SSH keys
- Support for private Git repositories via Personal Access Tokens (PAT)
- Branch and revision specification for deployments
- Automatic cleanup of cloned repositories after deployment

#### Modal Platform Integration

- Deploy Modal apps using the Modal CLI (`modal deploy`)
- Automatic extraction of app names from Python source files
- Query Modal API to retrieve app IDs for reliable tracking
- Smart deletion using app ID retrieval from CRD status, in-memory cache, or Modal API query
- Support for all Modal features (GPU, CPU, memory, concurrency, timeouts) defined in user app files
- Environment variable injection into Modal deployments
- Web app URL extraction and status reporting

#### Security & Access Control

- Kubernetes RBAC configuration with least privilege principle
- Secure credential management via Kubernetes secrets
- Support for Modal credentials (`MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`)
- Support for Git credentials (SSH keys and PATs)
- Non-root container execution (runs as user `operator`, UID 1000)
- Namespace-scoped secret references with cross-namespace support

#### Environment & Configuration

- Modal environment selection (`main`, `dev`, `staging`, `prod`)
- Environment variable configuration via CRD spec
- Kubernetes secret injection for sensitive values
- Configurable namespace watching (all namespaces or specific namespace)

#### Deployment & Operations

- Makefile with comprehensive deployment automation
- Automatic git commit-based Docker image tagging
- kind cluster auto-detection and image loading
- Kustomize overlays for development and production environments
- Automated installation with prerequisite checking
- Secret creation from `.env` file for local development

#### Monitoring & Observability

- Structured logging with INFO/WARNING/ERROR levels
- CRD status updates with detailed phase information
- Last deployment timestamp tracking
- Modal app ID storage in CRD status for cross-restart persistence
- Kubernetes event generation for lifecycle changes
- Custom printer columns for `kubectl get modaldeployments` (App Name, Phase, Environment, URL, Age)

#### Examples & Documentation

- Hello World example deployment
- GPU job example deployment
- Flask app example deployment
- Private repository example deployment
- Comprehensive README with quick start guide
- Architecture documentation with Mermaid diagrams
- Development guide with local setup instructions
- Contributing guidelines and code of conduct

#### Developer Experience

- Pre-commit hooks configuration for code quality
- Makefile targets for build, deploy, install, uninstall
- Test commands for validating examples
- Lint support with automatic hook installation
- `.env` file support for local credentials management
- Colored terminal output for better readability

### Implementation Details

#### Deployment Flow

1. Operator watches for `ModalDeployment` CRD changes
2. Clones Git repository with optional authentication
3. Extracts app name from Modal Python file
4. Executes `modal deploy` with user's source file
5. Waits for app registration in Modal's system
6. Queries Modal API to retrieve app ID
7. Stores app ID in CRD status for deletion tracking
8. Updates CRD status with deployment results and URL

#### Deletion Flow

1. Retrieves app ID from CRD status (persisted across restarts)
2. Falls back to in-memory cache if status unavailable
3. Queries Modal API as last resort using app name
4. Executes `modal app stop <app-id>` to terminate deployment
5. Cleans up local resources and cloned repositories
6. Removes entry from in-memory tracking

### Known Limitations

- Manual updates required (automatic git polling not yet implemented - see [Issue #5](https://github.com/mishraprafful/gitops-modal/issues/5))
- No Prometheus metrics exposure yet (planned - see [Issue #7](https://github.com/mishraprafful/gitops-modal/issues/7))
- No webhook validation for CRDs yet (planned - see [Issue #8](https://github.com/mishraprafful/gitops-modal/issues/8))

[Unreleased]: https://github.com/mishraprafful/gitops-modal/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mishraprafful/gitops-modal/releases/tag/v0.1.0
