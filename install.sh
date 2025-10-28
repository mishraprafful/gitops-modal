#!/bin/bash
set -euo pipefail

# Modal GitOps Operator Installation Script
# This script installs the Modal operator in a Kubernetes cluster

NAMESPACE="modal-system"
MODAL_TOKEN_ID="${MODAL_TOKEN_ID:-}"
MODAL_TOKEN_SECRET="${MODAL_TOKEN_SECRET:-}"
OPERATOR_IMAGE="${OPERATOR_IMAGE:-modal-operator:latest}"
WATCH_NAMESPACE="${WATCH_NAMESPACE:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is required but not installed"
        exit 1
    fi
    
    # Check cluster access
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot access Kubernetes cluster"
        exit 1
    fi
    
    # Check Modal credentials
    if [[ -z "$MODAL_TOKEN_ID" || -z "$MODAL_TOKEN_SECRET" ]]; then
        print_warning "Modal credentials not provided via environment variables"
        print_status "You will need to update the secret manually after installation"
    fi
    
    print_success "Prerequisites check passed"
}

create_namespace() {
    print_status "Creating namespace $NAMESPACE..."
    
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        print_warning "Namespace $NAMESPACE already exists"
    else
        kubectl create namespace "$NAMESPACE"
        print_success "Namespace $NAMESPACE created"
    fi
}

install_crd() {
    print_status "Installing ModalDeployment CRD..."
    
    kubectl apply -f crds/modaldeployment-crd.yaml
    
    # Wait for CRD to be established
    print_status "Waiting for CRD to be established..."
    kubectl wait --for condition=established --timeout=60s crd/modaldeployments.modal.io
    
    print_success "CRD installed successfully"
}

create_secrets() {
    print_status "Creating secrets..."
    
    if [[ -n "$MODAL_TOKEN_ID" && -n "$MODAL_TOKEN_SECRET" ]]; then
        # Create Modal credentials secret
        kubectl create secret generic modal-credentials \
            --namespace="$NAMESPACE" \
            --from-literal=token-id="$MODAL_TOKEN_ID" \
            --from-literal=token-secret="$MODAL_TOKEN_SECRET" \
            --dry-run=client -o yaml | kubectl apply -f -
        
        print_success "Modal credentials secret created"
    else
        print_warning "Skipping Modal credentials secret creation"
        print_status "Run the following commands to create the secret manually:"
        echo "kubectl create secret generic modal-credentials \\"
        echo "  --namespace=$NAMESPACE \\"
        echo "  --from-literal=token-id=YOUR_MODAL_TOKEN_ID \\"
        echo "  --from-literal=token-secret=YOUR_MODAL_TOKEN_SECRET"
    fi
}

install_rbac() {
    print_status "Installing RBAC resources..."
    
    kubectl apply -f manifests/rbac.yaml
    
    print_success "RBAC resources installed"
}

install_operator() {
    print_status "Installing Modal operator..."
    
    # Update deployment with custom image and namespace settings
    if [[ -n "$WATCH_NAMESPACE" ]]; then
        print_status "Configuring operator to watch namespace: $WATCH_NAMESPACE"
        kubectl patch deployment modal-operator \
            -n "$NAMESPACE" \
            -p '{"spec":{"template":{"spec":{"containers":[{"name":"operator","env":[{"name":"WATCH_NAMESPACE","value":"'$WATCH_NAMESPACE'"}]}]}}}}' \
            --dry-run=client -o yaml > /tmp/deployment-patch.yaml
    fi
    
    if [[ "$OPERATOR_IMAGE" != "modal-operator:latest" ]]; then
        print_status "Using custom operator image: $OPERATOR_IMAGE"
        sed "s|image: modal-operator:latest|image: $OPERATOR_IMAGE|g" manifests/deployment.yaml | kubectl apply -f -
    else
        kubectl apply -f manifests/deployment.yaml
    fi
    
    print_success "Operator deployment created"
}

wait_for_operator() {
    print_status "Waiting for operator to be ready..."
    
    kubectl wait --for=condition=available --timeout=300s deployment/modal-operator -n "$NAMESPACE"
    
    # Check operator logs
    print_status "Checking operator status..."
    if kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=modal-operator | grep -q Running; then
        print_success "Modal operator is running successfully"
    else
        print_error "Modal operator failed to start"
        print_status "Check logs with: kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=modal-operator"
        exit 1
    fi
}

verify_installation() {
    print_status "Verifying installation..."
    
    # Check CRD
    if kubectl get crd modaldeployments.modal.io &> /dev/null; then
        print_success "✓ ModalDeployment CRD is installed"
    else
        print_error "✗ ModalDeployment CRD is missing"
    fi
    
    # Check operator deployment
    if kubectl get deployment modal-operator -n "$NAMESPACE" &> /dev/null; then
        print_success "✓ Modal operator deployment exists"
    else
        print_error "✗ Modal operator deployment is missing"
    fi
    
    # Check operator pod
    if kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=modal-operator | grep -q Running; then
        print_success "✓ Modal operator pod is running"
    else
        print_warning "⚠ Modal operator pod is not running"
    fi
    
    # Check secrets
    if kubectl get secret modal-credentials -n "$NAMESPACE" &> /dev/null; then
        print_success "✓ Modal credentials secret exists"
    else
        print_warning "⚠ Modal credentials secret is missing"
    fi
}

print_next_steps() {
    print_success "Installation completed!"
    echo ""
    echo "Next steps:"
    echo "1. If you haven't already, create the Modal credentials secret:"
    echo "   kubectl create secret generic modal-credentials \\"
    echo "     --namespace=$NAMESPACE \\"
    echo "     --from-literal=token-id=YOUR_MODAL_TOKEN_ID \\"
    echo "     --from-literal=token-secret=YOUR_MODAL_TOKEN_SECRET"
    echo ""
    echo "2. Deploy a sample ModalDeployment:"
    echo "   kubectl apply -f examples/function-deployment.yaml"
    echo ""
    echo "3. Check the status:"
    echo "   kubectl get modaldeployments"
    echo "   kubectl describe modaldeployment hello-world-function"
    echo ""
    echo "4. View operator logs:"
    echo "   kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=modal-operator -f"
}

main() {
    echo "Modal GitOps Operator Installation"
    echo "=================================="
    echo ""
    
    check_prerequisites
    create_namespace
    install_crd
    create_secrets
    install_rbac
    install_operator
    wait_for_operator
    verify_installation
    print_next_steps
}

# Handle script arguments
case "${1:-install}" in
    "install")
        main
        ;;
    "uninstall")
        print_status "Uninstalling Modal operator..."
        kubectl delete -f manifests/ --ignore-not-found=true
        kubectl delete -f crds/ --ignore-not-found=true
        kubectl delete namespace "$NAMESPACE" --ignore-not-found=true
        print_success "Modal operator uninstalled"
        ;;
    "status")
        verify_installation
        ;;
    *)
        echo "Usage: $0 [install|uninstall|status]"
        echo "  install   - Install the Modal operator (default)"
        echo "  uninstall - Remove the Modal operator"
        echo "  status    - Check installation status"
        exit 1
        ;;
esac
