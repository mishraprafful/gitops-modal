# Modal GitOps Operator

A Kubernetes operator that enables GitOps-style deployments to [Modal](https://modal.com) using Custom Resource Definitions (CRDs). Deploy and manage Modal applications declaratively through Kubernetes manifests.

## Features

- 🚀 **Declarative Deployments**: Define Modal applications using Kubernetes CRDs
- 🔄 **GitOps Workflow**: Integrate with ArgoCD, Flux, or other GitOps tools
- 🎯 **Multi-Environment Support**: Deploy to different Modal environments (dev, staging, prod)
- 📊 **Resource Management**: Configure CPU, memory, GPU, and scaling parameters
- 🔐 **Secret Management**: Secure handling of Modal secrets and Kubernetes secrets
- ⏰ **Scheduled Jobs**: Support for cron-based scheduled functions
- 🌐 **Web Applications**: Deploy FastAPI and other web apps with webhooks
- 🔍 **Status Monitoring**: Real-time status updates and health checks

## Quick Start

### Prerequisites

- Kubernetes cluster (1.19+)
- kubectl configured
- Modal account with API credentials
- Modal CLI installed (`pip install modal`)
- Docker (for building custom operator image)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/gitops-modal
   cd gitops-modal
   ```

2. **Set up Modal credentials:**
   ```bash
   export MODAL_TOKEN_ID="your-modal-token-id"
   export MODAL_TOKEN_SECRET="your-modal-token-secret"
   ```

3. **Install the operator:**
   ```bash
   ./install.sh
   ```

4. **Verify installation:**
   ```bash
   kubectl get modaldeployments
   kubectl get pods -n modal-system
   ```

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
  memory: "2Gi"                 # Memory allocation
  gpu: "A100"                   # GPU type: T4, A10G, A100, H100
  gpuCount: 2                   # Number of GPUs
  timeout: 300                  # Function timeout (seconds)
```

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
    image:
      name: "your-registry/ml-training"
      tag: "v1.2.0"
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
    gpu: "A100"
    gpuCount: 2
    timeout: 7200
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

## Monitoring and Observability

### Status Monitoring

Check deployment status:
```bash
# List all deployments
kubectl get modaldeployments

# Get detailed status
kubectl describe modaldeployment my-app

# Watch for changes
kubectl get modaldeployments -w
```

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
   kubectl create secret generic modal-credentials \
     --namespace=modal-system \
     --from-literal=token-id=YOUR_TOKEN_ID \
     --from-literal=token-secret=YOUR_TOKEN_SECRET
   ```

2. **Git repository access issues**
   - Ensure repository is public or provide SSH keys
   - Check network policies if using private clusters

3. **Operator pod crash loop**
   ```bash
   kubectl logs -n modal-system -l app.kubernetes.io/name=modal-operator
   ```

4. **CRD not found**
   ```bash
   kubectl apply -f crds/modaldeployment-crd.yaml
   ```

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

## Development

### Building the Operator

```bash
# Build and test Docker image (recommended)
./build.sh

# Or build manually
docker build -t modal-operator:latest -f operator/Dockerfile operator/

# Run locally (for development)
cd operator
pip install -r requirements.txt
export MODAL_TOKEN_ID="your-token"
export MODAL_TOKEN_SECRET="your-secret"
python setup_modal.py  # Setup Modal CLI
python main.py          # Start operator
```

**Docker Image Features:**
- ✅ Modal CLI pre-installed and configured
- ✅ Git support for repository cloning  
- ✅ Proper user permissions and security
- ✅ Automatic Modal authentication setup
- ✅ Health checks and error handling

### Testing

```bash
# Apply test deployment
kubectl apply -f examples/function-deployment.yaml

# Check status
kubectl get modaldeployments
kubectl logs -n modal-system -l app.kubernetes.io/name=modal-operator
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

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
