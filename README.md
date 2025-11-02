# Modal GitOps Operator

Deploy [Modal](https://modal.com) applications declaratively using Kubernetes CRDs. Enable GitOps workflows with ArgoCD, Flux, or any GitOps tool.

## What It Does

- 📦 **Deploy Modal apps from Git** - Just point to your Modal Python file
- 🔄 **GitOps-ready** - Works with ArgoCD, Flux, and other GitOps tools
- 🎯 **Smart deletion** - Tracks app IDs for reliable cleanup
- 🔐 **Secure** - Supports private repos (SSH/PAT) and Kubernetes secrets
- 📊 **Status tracking** - Real-time deployment status in Kubernetes

## Quick Start

### 1. Prerequisites

- Kubernetes cluster (kind recommended for local testing)
- [Modal account](https://modal.com) with API credentials
- kubectl configured

### 2. Install

```bash
# Clone repository
git clone https://github.com/your-org/gitops-modal
cd gitops-modal

# Create .env with your Modal credentials
cat > .env << EOF
MODAL_TOKEN_ID=your-modal-token-id
MODAL_TOKEN_SECRET=your-modal-token-secret
EOF

# Build and deploy (for kind clusters - auto-loads image)
make deploy

# For other clusters, push to registry first:
make build IMAGE=your-registry/modal-operator:v1.0.0
docker push your-registry/modal-operator:v1.0.0
make install IMAGE=your-registry/modal-operator:v1.0.0
```

### 3. Deploy Your First App

Create a Modal app file (`hello.py`):

```python
import modal

app = modal.App("hello-world")

@app.function()
def hello():
    print("Hello from Modal!")
    return "Hello World"
```

Create a deployment:

```yaml
apiVersion: modal.io/v1
kind: ModalDeployment
metadata:
  name: hello-world
spec:
  appName: hello-world
  source:
    git:
      repository: "https://github.com/your-org/modal-apps"
      branch: "main"
      path: "hello.py"
  environment:
    name: "main"
```

Deploy it:

```bash
kubectl apply -f deployment.yaml

# Check status
kubectl get modaldeployments
kubectl describe modaldeployment hello-world

# To update: manually reapply or use kubectl edit
kubectl apply -f deployment.yaml  # After making changes
```

> **Note**: The operator currently requires manual updates (reapply the CRD). Automatic git polling and reconciliation is planned - see [Issue #5](https://github.com/mishraprafful/gitops-modal/issues/5)

## Configuration

### Source from Git

```yaml
spec:
  appName: my-app
  source:
    git:
      repository: "https://github.com/org/repo"
      branch: "main"           # Optional, default: main
      path: "path/to/app.py"   # Your Modal app file
```

### Private Repositories

**SSH Key:**

```bash
# Create secret
kubectl create secret generic git-ssh-credentials \
  --from-file=ssh-privatekey=$HOME/.ssh/deploy_key
```

```yaml
source:
  git:
    repository: "git@github.com:org/private-repo.git"
    path: "app.py"
    credentials:
      secretRef:
        name: git-ssh-credentials
```

**Personal Access Token:**

```bash
# Add to .env file
echo "GITHUB_TOKEN=ghp_your_token" >> .env
make install  # Automatically creates secret
```

```yaml
source:
  git:
    repository: "https://github.com/org/private-repo.git"
    path: "app.py"
    credentials:
      secretRef:
        name: git-credentials
```

### Environment Variables & Secrets

```yaml
environment:
  name: "main"  # Modal environment: main, dev, staging, prod
  variables:
    LOG_LEVEL: "INFO"
    API_URL: "https://api.example.com"
  secrets:
    - name: "db-credentials"
      secretRef:
        name: "database-secret"
```

### Compute, GPU, Scaling

**Define in your Modal app file, not the CRD:**

```python
import modal

app = modal.App("my-app")
image = modal.Image.debian_slim().pip_install("torch")

@app.function(
    image=image,
    cpu=2,                  # CPU cores
    memory=4096,            # Memory in MB
    gpu="A100",             # GPU type
    timeout=3600,           # Seconds
    concurrency_limit=10,   # Max concurrent instances
)
def my_function():
    # Your code here
    pass
```

See [Modal docs](https://modal.com/docs) for complete API reference.

## Examples

```bash
# Deploy examples
kubectl apply -f examples/hello-world-deployment.yaml
kubectl apply -f examples/gpu-job-deployment.yaml
kubectl apply -f examples/fastapi-app-deployment.yaml

# Deploy all examples
kubectl apply -f examples/
```

## GitOps Integration

### ArgoCD

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

### Flux

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
```

### Kustomize

```bash
# Development environment
kubectl apply -k kustomize/overlays/development

# Production environment
kubectl apply -k kustomize/overlays/production
```

## How It Works

> 📐 **See [ARCHITECTURE.md](ARCHITECTURE.md)** for detailed architecture diagrams, data flows, and design decisions.

```
┌─────────────────┐
│  Kubernetes     │
│  ModalDeployment│
│  CRD            │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Modal GitOps Operator                  │
│  ┌───────────────────────────────────┐  │
│  │ 1. Clone Git repo                 │  │
│  │ 2. Deploy to Modal (modal deploy) │  │
│  │ 3. Query app ID (modal app list)  │  │
│  │ 4. Store ID in CRD status        │  │
│  └───────────────────────────────────┘  │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Modal Platform │
│  - Deployed App │
│  - App ID       │
└─────────────────┘
```

**Deployment Flow:**

1. Operator watches ModalDeployment CRDs
2. Clones your Git repository
3. Runs `modal deploy` on your app file
4. Queries Modal for the app ID
5. Stores app ID in CRD status
6. Updates status with URL and deployment info

**Deletion Flow:**

1. Retrieves app ID from CRD status
2. Runs `modal app stop <app-id>`
3. Cleans up local resources

## Monitoring

```bash
# Check deployments
kubectl get modaldeployments
kubectl describe modaldeployment my-app

# View operator logs
kubectl logs -n modal-operator -l app=modal-operator -f

# Check status
kubectl get modaldeployment my-app -o jsonpath='{.status}'
```

**Status Fields:**

- `phase` - Deploying, Ready, Failed, Terminating
- `modalAppId` - Modal app identifier (for deletion)
- `url` - App webhook URL (if applicable)
- `lastDeployment` - Last deployment timestamp

## Troubleshooting

**Modal credentials not found:**

```bash
kubectl create secret generic modal-credentials \
  --namespace=modal-operator \
  --from-literal=MODAL_TOKEN_ID=xxx \
  --from-literal=MODAL_TOKEN_SECRET=yyy
```

**Git access issues:**

- Verify repository is public or SSH key is configured
- Check secret exists: `kubectl get secret git-ssh-credentials`

**Deletion not working:**

- Check `status.modalAppId` is populated: `kubectl get modaldeployment <name> -o yaml`
- View operator logs for errors

**See full logs:**

```bash
kubectl logs -n modal-operator -l app=modal-operator -f
kubectl describe modaldeployment <name>
```

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for:

- Local development setup with kind
- Building and testing
- Architecture details
- Contributing guidelines

**Quick dev setup:**

```bash
# Create kind cluster
kind create cluster --name modal-dev

# Build and deploy
make deploy

# View logs
kubectl logs -n modal-operator -l app=modal-operator -f
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Support

- [GitHub Issues](https://github.com/mishraprafful/gitops-modal/issues)
- [Discussions](https://github.com/mishraprafful/gitops-modal/discussions)
