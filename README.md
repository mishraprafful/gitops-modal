# Modal GitOps Operator

A Kubernetes operator that enables GitOps-style deployments to [Modal](https://modal.com) using Custom Resource Definitions (CRDs). Deploy and manage Modal applications declaratively through Kubernetes manifests.

## Features

- 🚀 **Declarative Deployments**: Define Modal applications using Kubernetes CRDs
- 🔄 **GitOps Workflow**: Integrate with ArgoCD, Flux, or other GitOps tools
- 🔄 **Update Support**: Automatically update deployments when CRD specs change
- 🗑️ **Delete Support**: Properly stop and clean up Modal apps on resource deletion
- 🎯 **Multi-Environment Support**: Deploy to different Modal environments (dev, staging, prod)
- 📊 **Resource Management**: Configure CPU, memory, GPU, and scaling parameters
- 🎮 **GPU Support**: Full support for all Modal GPU types (T4, L4, A10, A100, H100, H200, B200, and more)
- 🔐 **Secret Management**: Secure handling of Modal secrets and Kubernetes secrets
- ⏰ **Scheduled Jobs**: Support for cron-based scheduled functions
- 🌐 **Web Applications**: Deploy FastAPI and other web apps with webhooks
- 🔍 **Status Monitoring**: Real-time status updates and health checks
- 💾 **Persistent State**: App IDs stored in CRD status for reliable deletion across operator restarts

## Quick Start

### Prerequisites

- Kubernetes cluster (1.19+)
  - **Recommended for local testing: [kind](https://kind.sigs.k8s.io/)** (Kubernetes in Docker)
  - The Makefile automatically detects kind clusters and loads images for you
- kubectl configured
- Modal account with API credentials
- Docker (for building custom operator image)

### Installation

#### Quick Start with kind (Recommended for Testing)

[kind](https://kind.sigs.k8s.io/) is the recommended way to test this operator locally. The Makefile automatically detects kind clusters and loads images for you.

1. **Set up a kind cluster:**

   ```bash
   # Install kind (if not already installed)
   # macOS: brew install kind
   # Linux: See https://kind.sigs.k8s.io/docs/user/quick-start/#installation

   # Create a kind cluster
   kind create cluster --name modal-test

   # Verify cluster is running
   kubectl cluster-info --context kind-modal-test
   ```

2. **Clone the repository:**

   ```bash
   git clone https://github.com/your-org/gitops-modal
   cd gitops-modal
   ```

3. **Set up Modal credentials (optional - can use .env file):**

   ```bash
   # Create .env file with your Modal credentials
   cat > .env << EOF
   MODAL_TOKEN_ID=your-modal-token-id
   MODAL_TOKEN_SECRET=your-modal-token-secret
   EOF
   ```

4. **Build and install:**

   ```bash
   # Option 1: Build and install in one command (recommended)
   make deploy

   # Option 2: Build and install separately
   make build
   make install
   ```

The Makefile will automatically:

- Detect if you're using a kind cluster
- Load the Docker image into kind (no need to push to a registry!)
- Install the operator with the correct image

#### Installation on Other Clusters

For non-kind clusters, you'll need to push your image to a container registry:

1. **Build the operator image:**

   ```bash
   # Build with custom image name (include your registry)
   make build IMAGE=your-registry.io/modal-operator:v1.0.0

   # Push to registry
   docker push your-registry.io/modal-operator:v1.0.0
   ```

2. **Install the operator:**

   ```bash
   # Install with your image and Modal credentials
   make install IMAGE=your-registry.io/modal-operator:v1.0.0 \
     MODAL_TOKEN_ID="your-token-id" \
     MODAL_TOKEN_SECRET="your-token-secret"

   # Or use .env file for credentials
   make install IMAGE=your-registry.io/modal-operator:v1.0.0
   ```

4. **Verify installation:**

   ```bash
   kubectl get modaldeployments
   kubectl get pods -n modal-system
   ```

5. **Uninstall (if needed):**

   ```bash
   make uninstall
   ```

**Note:** The `make install` command automatically updates the image name in `manifests/deployment.yaml` to match the image you built. This ensures the deployment uses your built image.

**For development:** See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed development setup, building, testing, and contribution guidelines.

### Deploy Your First Modal App

1. **Create a simple function deployment:**

   ```yaml
   apiVersion: modal.io/v1
   kind: ModalDeployment
   metadata:
     name: hello-world
   spec:
     appName: hello-world-function
     description: "My first Modal function via GitOps"
     source:
       git:
         repository: "https://github.com/your-org/modal-apps"
         branch: "main"
         path: "functions/hello_world.py"
     environment:
       name: "main"
     compute:
       cpu: "0.25"
       memory: "512Mi"
   ```

2. **Apply the deployment:**

   ```bash
   kubectl apply -f your-deployment.yaml
   ```

3. **Check status:**

   ```bash
   kubectl get modaldeployment hello-world
   kubectl describe modaldeployment hello-world
   ```

4. **Update the deployment:**

   ```bash
   # Edit the YAML file and reapply
   kubectl edit modaldeployment hello-world
   # Or apply updated YAML
   kubectl apply -f your-deployment.yaml
   ```

5. **Delete the deployment:**

   ```bash
   kubectl delete modaldeployment hello-world
   # The operator will automatically stop the Modal app
   ```

## Configuration Reference

### ModalDeployment Spec

| Field         | Type   | Description                           | Required |
| ------------- | ------ | ------------------------------------- | -------- |
| `appName`     | string | Name of the Modal application         | ✅        |
| `description` | string | Description of the application        | ❌        |
| `source`      | object | Source configuration (git or image)   | ✅        |
| `environment` | object | Environment and secrets configuration | ❌        |
| `compute`     | object | CPU, memory, GPU configuration        | ❌        |
| `scaling`     | object | Auto-scaling parameters               | ❌        |
| `schedule`    | object | Cron schedule for scheduled functions | ❌        |
| `webhooks`    | object | Webhook configuration for web apps    | ❌        |
| `deployment`  | object | Deployment strategy and health checks | ❌        |

### Source Configuration

#### Git Source

```yaml
source:
  git:
    repository: "https://github.com/your-org/modal-apps"
    branch: "main"              # Optional, default: main
    path: "path/to/app.py"      # Path to Modal app file
    revision: "commit-sha"      # Optional, specific commit
```

#### Container Image Source

```yaml
source:
  image:
    name: "your-registry/modal-app"
    tag: "v1.0.0"              # Optional, default: latest
    pullSecret: "registry-creds" # Optional
```

### Environment Configuration

Configure environment variables and secrets for your Modal applications.

**Priority Order (highest to lowest):**

1. Kubernetes secrets
2. Explicit `variables` in YAML
3. Default values

```yaml
environment:
  name: "main"                  # Modal environment: main, dev, staging, prod
  variables:
    LOG_LEVEL: "INFO"
    API_URL: "https://api.example.com"
  secrets:
  - name: "db-credentials"      # Modal secret name
    secretRef:
      name: "database-secret"   # Kubernetes secret name
      namespace: "default"      # Optional, defaults to resource namespace
```

### Compute Configuration

```yaml
compute:
  cpu: "1"                      # CPU allocation (cores)
  memory: "2Gi"                 # Memory allocation (e.g., "512Mi", "1Gi", "2Ti")
  gpu: "A100"                   # GPU type (see supported types below)
  gpuCount: 2                   # Number of GPUs (1-8)
  timeout: 300                  # Function timeout in seconds (1-86400)
```

**Supported GPU Types:**

- `T4` - NVIDIA T4 GPU
- `L4` - NVIDIA L4 GPU
- `A10` - NVIDIA A10 GPU
- `A100` - NVIDIA A100 GPU
- `A100-40GB` - NVIDIA A100 GPU (40GB memory)
- `A100-80GB` - NVIDIA A100 GPU (80GB memory)
- `L40S` - NVIDIA L40S GPU
- `H100/H100!` - NVIDIA H100 GPU
- `H200` - NVIDIA H200 GPU
- `B200` - NVIDIA B200 GPU

### Scaling Configuration

```yaml
scaling:
  minInstances: 0               # Minimum instances (0 for serverless)
  maxInstances: 50              # Maximum instances
  concurrency: 10               # Requests per instance
  idleTimeout: 300              # Idle timeout before scale down
```

### Schedule Configuration

```yaml
schedule:
  cron: "0 2 * * *"            # Cron expression (daily at 2 AM)
  timezone: "UTC"               # Timezone
```

### Webhook Configuration

```yaml
webhooks:
  enabled: true
  path: "/"                     # Webhook path
  methods: ["GET", "POST"]      # HTTP methods
```

## Examples

### Web Application (FastAPI)

```yaml
apiVersion: modal.io/v1
kind: ModalDeployment
metadata:
  name: fastapi-web-app
spec:
  appName: fastapi-web-app
  description: "FastAPI web application"
  source:
    git:
      repository: "https://github.com/your-org/modal-apps"
      path: "web/fastapi_app.py"
  environment:
    name: "prod"
    variables:
      DATABASE_URL: "postgresql://..."
    secrets:
    - name: "db-credentials"
      secretRef:
        name: "database-secret"
  compute:
    cpu: "1"
    memory: "1Gi"
  scaling:
    minInstances: 2
    maxInstances: 50
    concurrency: 10
  webhooks:
    enabled: true
    path: "/"
    methods: ["GET", "POST", "PUT", "DELETE"]
```

### GPU ML Training Job

```yaml
apiVersion: modal.io/v1
kind: ModalDeployment
metadata:
  name: ml-training-job
spec:
  appName: ml-training-job
  description: "Machine learning training with GPU"
  source:
    git:
      repository: "https://github.com/your-org/ml-training"
      path: "training/train_model.py"
  environment:
    name: "main"
    variables:
      MODEL_TYPE: "transformer"
      BATCH_SIZE: "32"
    secrets:
    - name: "wandb-api-key"
      secretRef:
        name: "ml-secrets"
  compute:
    cpu: "4"
    memory: "16Gi"
    gpu: "A100-80GB"        # Use A100-80GB for larger models
    gpuCount: 2             # Use 2 GPUs for training
    timeout: 7200           # 2 hours timeout
```

### High-Performance GPU Job (H100)

```yaml
apiVersion: modal.io/v1
kind: ModalDeployment
metadata:
  name: llm-inference
spec:
  appName: llm-inference
  description: "LLM inference with H100 GPU"
  source:
    git:
      repository: "https://github.com/your-org/llm-inference"
      path: "inference/main.py"
  compute:
    cpu: "8"
    memory: "64Gi"
    gpu: "H100"             # H100 for maximum performance
    gpuCount: 1
    timeout: 3600
```

### Scheduled Data Pipeline

```yaml
apiVersion: modal.io/v1
kind: ModalDeployment
metadata:
  name: daily-data-pipeline
spec:
  appName: daily-data-pipeline
  description: "Daily ETL pipeline"
  source:
    git:
      repository: "https://github.com/your-org/data-pipelines"
      path: "pipelines/daily_etl.py"
  environment:
    name: "prod"
    secrets:
    - name: "aws-credentials"
      secretRef:
        name: "aws-secret"
  compute:
    cpu: "2"
    memory: "4Gi"
  schedule:
    cron: "0 2 * * *"
    timezone: "UTC"
```

## GitOps Integration

### Kustomize Support

The operator includes Kustomize support for environment-specific deployments:

```bash
# Base installation
kubectl apply -k manifests/

# Development environment (lower resources, DEBUG logging)
kubectl apply -k kustomize/overlays/development

# Production environment (HA, higher resources, INFO logging)
kubectl apply -k kustomize/overlays/production
```

The base `manifests/kustomization.yaml` includes all common resources. Overlays can customize:

- Image tags and registries
- Resource limits and requests
- Replica counts
- Environment variables
- Namespace settings

See [kustomize/README.md](kustomize/README.md) for more details on creating custom overlays.

### ArgoCD Integration

1. **Create ArgoCD Application:**

   ```yaml
   apiVersion: argoproj.io/v1alpha1
   kind: Application
   metadata:
     name: modal-deployments
   spec:
     source:
       repoURL: https://github.com/your-org/modal-configs
       targetRevision: main
       path: deployments
     destination:
       server: https://kubernetes.default.svc
     syncPolicy:
       automated:
         prune: true
         selfHeal: true
   ```

2. **Directory structure:**

   ```
   modal-configs/
   ├── deployments/
   │   ├── production/
   │   │   ├── web-app.yaml
   │   │   └── api-service.yaml
   │   ├── staging/
   │   │   ├── web-app.yaml
   │   │   └── api-service.yaml
   │   └── development/
   │       └── test-function.yaml
   ```

### Flux Integration

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1beta2
kind: Kustomization
metadata:
  name: modal-deployments
spec:
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: modal-configs
  path: "./deployments"
  prune: true
  validation: client
```

## Lifecycle Management

### Create, Update, and Delete

The operator supports the full lifecycle of Modal deployments:

**Create:**

```bash
kubectl apply -f deployment.yaml
```

**Update:**

```bash
# Edit the YAML and reapply, or use kubectl edit
kubectl edit modaldeployment my-app
kubectl apply -f updated-deployment.yaml
```

The operator automatically detects changes and redeploys to Modal. Modal handles versioning internally, so updates to the same app name will update the existing deployment.

**Delete:**

```bash
kubectl delete modaldeployment my-app
```

The operator will:

- Retrieve the Modal app ID from the CRD status (persists across operator restarts)
- Stop the Modal app using `modal app stop`
- Clean up local resources
- Allow the Kubernetes resource deletion to complete

## Monitoring and Observability

### Status Monitoring

Check deployment status:

```bash
# List all deployments with status
kubectl get modaldeployments

# Get detailed status including Modal app ID and URL
kubectl describe modaldeployment my-app

# Watch for changes
kubectl get modaldeployments -w

# Check status field for Modal app information
kubectl get modaldeployment my-app -o jsonpath='{.status}'
```

**Status Fields:**

- `phase`: Current phase (Deploying, Ready, Failed, Terminating)
- `modalAppId`: Modal app identifier (stored for reliable deletion)
- `url`: Modal app webhook URL (if webhooks enabled)
- `lastDeployment`: Timestamp of last deployment
- `conditions`: Detailed conditions with timestamps

### Operator Logs

```bash
# View operator logs
kubectl logs -n modal-system -l app.kubernetes.io/name=modal-operator -f

# Check specific deployment events
kubectl get events --field-selector involvedObject.name=my-app
```

### Metrics and Alerts

The operator exposes Prometheus metrics on port 8080:

- `modal_deployments_total` - Total number of Modal deployments
- `modal_deployments_ready` - Number of ready deployments  
- `modal_deployment_reconcile_duration` - Time spent reconciling deployments

Example Prometheus configuration:

```yaml
- job_name: 'modal-operator'
  kubernetes_sd_configs:
  - role: pod
    namespaces:
      names: ['modal-system']
  relabel_configs:
  - source_labels: [__meta_kubernetes_pod_label_app_kubernetes_io_name]
    action: keep
    regex: modal-operator
```

## Troubleshooting

### Common Issues

1. **Modal credentials not found**

   ```bash
   # Set as environment variables in the operator deployment
   kubectl create secret generic modal-credentials \
     --namespace=modal-system \
     --from-literal=MODAL_TOKEN_ID=YOUR_TOKEN_ID \
     --from-literal=MODAL_TOKEN_SECRET=YOUR_TOKEN_SECRET
   ```

2. **Git repository access issues**
   - Ensure repository is public or provide SSH keys
   - Check network policies if using private clusters
   - Verify git is available in the operator container

3. **Modal CLI not found**
   - Ensure Modal CLI is installed in the operator image
   - Check operator logs for Modal CLI availability
   - Verify `modal` command is in PATH

4. **GPU configuration not applied**
   - Verify GPU type matches supported enum values exactly (case-sensitive)
   - Check that `gpuCount` is between 1-8
   - Review generated Modal app script for GPU configuration

5. **App deletion not working**
   - Check that `status.modalAppId` is populated in the CRD
   - Verify Modal CLI is accessible
   - Check operator logs for deletion errors
   - Note: Deletion continues even if Modal cleanup fails (non-blocking)

6. **Operator pod crash loop**

   ```bash
   kubectl logs -n modal-system -l app.kubernetes.io/name=modal-operator
   kubectl describe pod -n modal-system -l app.kubernetes.io/name=modal-operator
   ```

7. **CRD not found**

   ```bash
   kubectl apply -f crds/modaldeployment-crd.yaml
   ```

8. **Function name issues**
   - If existing Modal apps have function names like `f`, they will be preserved
   - New wrapped apps will use `main()` as the function name
   - Check generated `modal_app.py` script for function definitions

### Debug Commands

```bash
# Check operator status
kubectl get pods -n modal-system
kubectl describe deployment modal-operator -n modal-system

# Validate CRD
kubectl get crd modaldeployments.modal.io

# Check RBAC
kubectl auth can-i create modaldeployments --as=system:serviceaccount:modal-system:modal-operator

# View resource status
kubectl get modaldeployments -o wide
kubectl describe modaldeployment <name>
```

For more advanced debugging and development troubleshooting, see [DEVELOPMENT.md](DEVELOPMENT.md#debugging).

## Development

For development setup, building, testing, architecture details, and contributing guidelines, see [DEVELOPMENT.md](DEVELOPMENT.md).

**Quick start for developers:**

- Use [kind](https://kind.sigs.k8s.io/) for local development (recommended)
- Run `make deploy` to build and install in one step
- Images are automatically tagged with git commit SHA
- See [DEVELOPMENT.md](DEVELOPMENT.md) for full development guide

## Security Considerations

- Store Modal credentials in Kubernetes secrets
- Use RBAC to limit operator permissions
- Run operator with non-root user
- Enable pod security standards
- Regularly update dependencies

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- Documentation: [GitHub Wiki](https://github.com/your-org/gitops-modal/wiki)
- Issues: [GitHub Issues](https://github.com/your-org/gitops-modal/issues)
- Discussions: [GitHub Discussions](https://github.com/your-org/gitops-modal/discussions)
- Modal Community: [Modal Discord](https://discord.gg/modal)
