# Development Guide

This guide covers everything you need to know for developing the Modal GitOps Operator.

## Table of Contents

- [Local Development Setup](#local-development-setup)
- [Building the Operator](#building-the-operator)
- [Running Locally](#running-locally)
- [Testing](#testing)
- [Architecture](#architecture)
- [Development Workflow](#development-workflow)
- [Debugging](#debugging)
- [Makefile Reference](#makefile-reference)
- [Docker Image Details](#docker-image-details)

## Local Development Setup

### Pre-commit Hooks

This project uses [pre-commit](https://pre-commit.com/) to enforce code quality standards. Pre-commit hooks automatically check and format code before each commit.

**Installation:**

```bash
# Install pre-commit (if not already installed)
pip install pre-commit

# Run linters - hooks will be installed automatically if needed
make lint
```

**What it checks:**

- **Python**: Linting with `ruff` and formatting with `black`
- **YAML**: Syntax and style checking with `yamllint` (configured for Kubernetes)
- **Markdown**: Linting with `markdownlint-cli2`
- **General**: Trailing whitespace, end-of-file fixer, YAML/JSON validation

**Usage:**

```bash
# Run hooks manually on all files
pre-commit run --all-files

# Or use the Makefile target
make lint

# Hooks run automatically on git commit
# To skip hooks (not recommended): git commit --no-verify
```

**Update hooks:**

```bash
pre-commit autoupdate
```

### Recommended: kind (Kubernetes in Docker)

[kind](https://kind.sigs.k8s.io/) is the recommended way to develop and test this operator locally. The Makefile automatically detects kind clusters and loads images for you.

**Benefits of using kind:**

- ✅ No container registry needed - images load directly into the cluster
- ✅ Fast iteration - rebuild and reload in seconds
- ✅ Isolated testing environment
- ✅ Easy cleanup - just delete the cluster
- ✅ Automatic image loading - the Makefile handles it for you

### Setup Steps

1. **Install kind:**

   ```bash
   # macOS
   brew install kind

   # Linux - see https://kind.sigs.k8s.io/docs/user/quick-start/#installation
   ```

2. **Create a kind cluster:**

   ```bash
   kind create cluster --name modal-dev

   # Verify cluster is running
   kubectl cluster-info --context kind-modal-dev
   ```

3. **Set up environment:**

   ```bash
   # Clone repository
   git clone https://github.com/your-org/gitops-modal
   cd gitops-modal

   # Create .env file with Modal credentials (optional)
   cat > .env << EOF
   MODAL_TOKEN_ID=your-modal-token-id
   MODAL_TOKEN_SECRET=your-modal-token-secret
   EOF
   ```

4. **Build and deploy:**

   ```bash
   make deploy
   ```

## Building the Operator

### Automatic Image Tagging

The Makefile automatically tags images with git commit SHA:

- Clean git tree: `modal-operator:abc12345`
- Dirty git tree: `modal-operator:abc12345-dirty`
- Not in git: `modal-operator:latest`

### Build Commands

```bash
# Build and install in one command (recommended)
make deploy

# Build only (does not require cluster access)
make build

# Build with custom image name
make build IMAGE=your-registry/modal-operator:v1.0.0

# Build and install separately
make build
make install

# See all available make targets and variables
make help
```

### Build Process

The build process:

1. Builds Docker image with all dependencies
2. Runs tests (`test_modal.py`) - build fails if tests fail
3. Creates operator user with proper permissions
4. Sets up Modal CLI environment
5. If kind cluster detected, automatically loads image into cluster

## Running Locally

For rapid development, you can run the operator outside of Kubernetes:

```bash
cd operator

# Install dependencies
pip install -r requirements.txt

# Set up Modal credentials
export MODAL_TOKEN_ID="your-token"
export MODAL_TOKEN_SECRET="your-secret"

# Setup Modal CLI
python setup_modal.py

# Start operator
python main.py
```

**Note:** When running locally, the operator will use your local `kubectl` context. Make sure you have:

- Valid kubectl configuration
- Access to a Kubernetes cluster
- CRD installed: `kubectl apply -f ../crds/modaldeployment-crd.yaml`

## Testing

### Running Tests During Build

Tests are automatically run during Docker build. If any test fails, the build will fail:

- `test_modal.py` - Tests Modal package import and basic functionality

### Manual Testing

```bash
# Build the operator
make build

# Deploy a test ModalDeployment
kubectl apply -f examples/function-deployment.yaml

# Check status
kubectl get modaldeployments
kubectl describe modaldeployment hello-world-function

# View operator logs
kubectl logs -n modal-system -l app.kubernetes.io/name=modal-operator -f

# Clean up
kubectl delete -f examples/function-deployment.yaml
```

### Test Files

- `operator/test_modal.py` - Modal package import and API tests

## Architecture

### How It Works

#### Deployment Flow

1. **Watch for CRDs**: Operator watches for ModalDeployment CRDs using [Kopf](https://kopf.readthedocs.io/)

2. **On Create/Update**:
   - Clone git repository (or extract container image)
   - Extract app name from the Modal Python file (looks for `App("name")` pattern)
   - Deploy using `modal deploy <app-file>`
   - Wait 2 seconds for app to register in Modal's system
   - Query Modal API: `modal app list --json` to get all deployed apps
   - Find the deployed app by name and retrieve its app ID
   - Store app ID in CRD `status.modalAppId` for reliable deletion
   - Update CRD status with deployment results (URL, timestamp, conditions)

3. **Key Details**:
   - Modal app files are deployed as-is without modification
   - App name extracted from source file takes precedence over CRD `appName`
   - App ID (format: `ap-xxxxxxxxx`) is the unique identifier used for deletion

#### Update Flow

> **Current Limitation**: Updates require manually reapplying the CRD. Automatic git polling and reconciliation is tracked in [Issue #5](https://github.com/mishraprafful/gitops-modal/issues/5).

1. User manually updates and reapplies CRD spec
2. Operator detects changes to CRD spec
3. Re-runs full deployment process with updated configuration
4. Modal's `deploy` command updates existing apps (by name)
5. New app ID is retrieved and stored in status
6. CRD status updated with new deployment information

#### Delete Flow

**3-tier strategy for finding app ID:**

1. **Primary**: Retrieve app ID from CRD `status.modalAppId` (most reliable, persists across restarts)
2. **Fallback**: Check in-memory tracking (works within same operator session)
3. **Last Resort**: Query `modal app list --json` to find app by name

**Deletion process:**

- Once app ID is found: `modal app stop <app-id>`
- Clean up local resources (cloned repo)
- Remove from in-memory tracking
- Non-blocking: continues even if Modal cleanup fails

**Why app ID is critical:**

- User's Modal app name may differ from CRD `appName`
- App ID is unique and reliable across deployments
- Enables deletion even after operator restarts

### Key Components

- **`operator/main.py`** - Main operator entry point, Kopf event handlers
- **`operator/modal_controller.py`** - Core business logic for Modal deployments
- **`operator/utils.py`** - Utility functions (logging, validation)
- **`operator/health_server.py`** - HTTP server for Kubernetes health probes
- **`operator/setup_modal.py`** - Modal CLI setup script

### Operator Lifecycle

1. **Startup:**
   - Health server starts on port 8081
   - Initializes Modal client (checks credentials)
   - Initializes Kubernetes client (in-cluster or local config)
   - Marks operator as ready (readiness probe returns 200)
   - Starts watching for ModalDeployment CRDs

2. **Runtime:**
   - Watches for CRD events (create, update, delete)
   - Processes each event asynchronously
   - Updates CRD status with results

3. **Shutdown:**
   - Receives SIGTERM signal
   - Stops health server gracefully
   - Cleanup handlers run
   - Process exits

## Development Workflow

### Getting Started

1. Fork and clone the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Test locally with kind: `make deploy`
5. Run tests: `make build` (tests run during build)
6. Submit a pull request

### Code Style

- Follow PEP 8 for Python code
- Use type hints where appropriate
- Add docstrings to functions and classes
- Keep functions focused and small

**Code formatting is enforced by pre-commit hooks:**

- Python code is automatically formatted with `black` and linted with `ruff`
- YAML files are linted with `yamllint` (configured for Kubernetes manifests)
- Markdown files are linted with `markdownlint-cli2`

### Git Workflow

The Makefile automatically tags images with git commit SHA. If the git tree has uncommitted changes, the tag includes a `-dirty` suffix. This helps track exactly which code version is in each image.

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass: `make build`
6. Update documentation if needed
7. Submit a pull request

## Debugging

### Operator Pod Issues

```bash
# Check operator logs
kubectl logs -n modal-system -l app.kubernetes.io/name=modal-operator -f

# Check operator pod status
kubectl get pods -n modal-system
kubectl describe pod -n modal-system <pod-name>

# Check events
kubectl get events -n modal-system --sort-by='.lastTimestamp'

# Check CRD status
kubectl get modaldeployments -o yaml
```

### Health Check Issues

```bash
# Test health endpoints manually
kubectl port-forward -n modal-system deployment/modal-operator 8081:8081
curl http://localhost:8081/healthz
curl http://localhost:8081/readyz
```

### Modal Deployment Issues

```bash
# Check operator logs for deployment errors
kubectl logs -n modal-system -l app.kubernetes.io/name=modal-operator | grep -i error

# Check CRD status for error messages
kubectl describe modaldeployment <name>

# Check generated Modal app script (in operator logs)
kubectl logs -n modal-system -l app.kubernetes.io/name=modal-operator | grep -A 50 "modal_app.py"
```

### Local Debugging

When running locally:

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python main.py

# Test specific CRD operations
kubectl apply -f examples/function-deployment.yaml
# Watch operator logs in real-time
```

### Common Development Issues

1. **Image not loading into kind:**

   ```bash
   # Verify kind cluster
   kind get clusters

   # Check cluster name matches context
   kubectl config current-context

   # Manually load image
   make load-kind
   ```

2. **Tests failing during build:**
   - Check test output in build logs
   - Run tests manually: `cd operator && python test_modal.py`
   - Ensure all dependencies are installed

3. **Operator not starting:**
   - Check Modal credentials are set
   - Verify Kubernetes access
   - Check health server can bind to port 8081

## Makefile Reference

Run `make help` to see all available targets and variables with their descriptions.

### Common Usage Examples

```bash
# Build with auto-generated tag (uses git commit SHA)
make build

# Build with custom tag
make build IMAGE=my-registry/modal-operator:v1.0.0

# Deploy with specific namespace watching
make deploy WATCH_NAMESPACE=default

# Install with Modal credentials (or use .env file)
make install MODAL_TOKEN_ID=xxx MODAL_TOKEN_SECRET=yyy
```

## Docker Image Details

### Image Features

- ✅ Modal CLI pre-installed and configured
- ✅ Git support for repository cloning
- ✅ Proper user permissions and security (non-root operator user)
- ✅ Automatic Modal authentication setup via environment variables
- ✅ Health checks via HTTP endpoints (`/healthz`, `/readyz`)
- ✅ Error handling and logging

### Build Process

The Dockerfile builds a Python-based image that:

- Installs system dependencies (git, curl) and Python packages
- Runs tests during build (build fails if tests fail)
- Sets up non-root operator user with proper permissions
- Configures Modal CLI and health check endpoints

### Image Structure

```
/app
├── main.py              # Operator entry point
├── modal_controller.py  # Core business logic
├── utils.py            # Utilities
├── health_server.py    # Health check server
├── setup_modal.py      # Modal CLI setup
└── test_*.py           # Test files (included for build-time testing)
```

### Security

- Runs as non-root user (`operator`, UID 1000)
- Minimal base image (`python:3.11-slim`)
- Proper file permissions
- No unnecessary capabilities
- Read-only root filesystem disabled (Modal CLI needs to write config)
