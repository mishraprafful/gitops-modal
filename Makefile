# Modal GitOps Operator Makefile

# Image name and tag - can be overridden with make IMAGE=your-registry/modal-operator:v1.0.0
# If not set, will use git commit SHA and append -dirty if git tree is dirty
ifeq ($(IMAGE),)
  ifneq ($(shell command -v git > /dev/null 2>&1 && git rev-parse --git-dir > /dev/null 2>&1 && echo "yes"),)
    GIT_COMMIT := $(shell git rev-parse --short=8 HEAD 2>/dev/null || echo "unknown")
    ifeq ($(shell git diff --quiet HEAD 2>/dev/null && git diff --cached --quiet 2>/dev/null && echo "clean"),clean)
      IMAGE := modal-operator:$(GIT_COMMIT)
    else
      IMAGE := modal-operator:$(GIT_COMMIT)-dirty
    endif
  else
    IMAGE := modal-operator:latest
  endif
endif
NAMESPACE ?= modal-system
# WATCH_NAMESPACE - empty means watch all namespaces, or set to a specific namespace
WATCH_NAMESPACE ?=

# Load .env file if it exists (for local development)
# Format: MODAL_TOKEN_ID=value
#         MODAL_TOKEN_SECRET=value
ifneq (,$(wildcard .env))
    include .env
    export
endif

# Modal credentials - can be set via .env file, environment variables, or make arguments
MODAL_TOKEN_ID ?= 
MODAL_TOKEN_SECRET ?=

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

.PHONY: help build deploy install uninstall test clean update-image load-kind check-kind lint

help: ## Show this help message
	@echo "$(BLUE)Modal GitOps Operator Makefile$(NC)"
	@echo ""
	@echo "Usage: make [target] [VARIABLE=value...]"
	@echo ""
	@echo "Variables:"
	@echo "  IMAGE=$(IMAGE)              Docker image name and tag (auto-generated from git if not set)"
	@echo "  NAMESPACE=$(NAMESPACE)      Kubernetes namespace"
	@echo "  MODAL_TOKEN_ID=             Modal token ID (optional, can be in .env)"
	@echo "  MODAL_TOKEN_SECRET=         Modal token secret (optional, can be in .env)"
	@echo "  WATCH_NAMESPACE=            Namespace to watch (empty = all namespaces, or specify a namespace)"
	@echo ""
	@if [ -f .env ]; then \
		echo "$(GREEN)✓ .env file found and will be loaded$(NC)"; \
	else \
		echo "$(YELLOW)ℹ Tip: Create .env file with MODAL_TOKEN_ID and MODAL_TOKEN_SECRET$(NC)"; \
	fi
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

# Function to check if current cluster is kind
check-kind: ## Check if current Kubernetes cluster is kind
	@if command -v kubectl > /dev/null 2>&1 && kubectl cluster-info > /dev/null 2>&1; then \
		context=$$(kubectl config current-context 2>/dev/null || echo ""); \
		if [ -n "$$context" ] && echo "$$context" | grep -q "kind"; then \
			echo "kind"; \
		elif kubectl get nodes -o jsonpath='{.items[*].metadata.name}' 2>/dev/null | grep -q "kind"; then \
			echo "kind"; \
		else \
			echo "not-kind"; \
		fi \
	else \
		echo "not-kind"; \
	fi

load-kind: ## Load Docker image into kind cluster (if cluster is kind)
	@if command -v kind > /dev/null 2>&1; then \
		echo "$(BLUE)Checking if cluster is kind...$(NC)"; \
		if ! kubectl cluster-info > /dev/null 2>&1; then \
			echo "$(BLUE)No Kubernetes cluster accessible, skipping kind image load$(NC)"; \
		else \
			kind_cluster=""; \
			context=$$(kubectl config current-context 2>/dev/null || echo ""); \
			available_clusters=$$(kind get clusters 2>/dev/null || echo ""); \
			if [ -z "$$available_clusters" ]; then \
				echo "$(BLUE)No kind clusters found, skipping image load$(NC)"; \
			else \
				if [ -n "$$context" ] && echo "$$context" | grep -q "^kind-"; then \
					context_cluster=$$(echo "$$context" | sed 's/^kind-//'); \
					if echo "$$available_clusters" | grep -qw "$$context_cluster"; then \
						kind_cluster="$$context_cluster"; \
						echo "$(BLUE)Matched context to kind cluster: $$kind_cluster$(NC)"; \
					fi; \
				fi; \
				if [ -z "$$kind_cluster" ]; then \
					kind_cluster=$$(echo "$$available_clusters" | head -n1 | tr -d '[:space:]'); \
					echo "$(BLUE)Using first available kind cluster: $$kind_cluster$(NC)"; \
				fi; \
				if [ -n "$$kind_cluster" ]; then \
					echo "$(BLUE)Loading image $(IMAGE) into kind cluster: $$kind_cluster$(NC)"; \
					if kind load docker-image $(IMAGE) --name $$kind_cluster; then \
						echo "$(GREEN)✅ Image loaded into kind cluster: $$kind_cluster$(NC)"; \
					else \
						echo "$(RED)✗ Error: Failed to load image into kind cluster: $$kind_cluster$(NC)"; \
						echo "$(BLUE)   Verify cluster is running: kind get clusters$(NC)"; \
						echo "$(BLUE)   Check cluster nodes: kind get nodes --name $$kind_cluster$(NC)"; \
					fi; \
				fi; \
			fi; \
		fi \
	else \
		echo "$(BLUE)kind not installed, skipping image load$(NC)"; \
	fi

build: ## Build the Docker image (auto-tags with git commit SHA + -dirty if tree is dirty)
	@echo "$(BLUE)Building Modal GitOps Operator Docker image...$(NC)"
	@echo "$(BLUE)Image: $(IMAGE)$(NC)"
	@if command -v git > /dev/null 2>&1 && git rev-parse --git-dir > /dev/null 2>&1; then \
		commit=$$(git rev-parse --short=8 HEAD 2>/dev/null || echo "unknown"); \
		echo "$(BLUE)Git commit: $$commit$(NC)"; \
		if ! git diff --quiet HEAD 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then \
			echo "$(YELLOW)⚠ Git tree is dirty - image tagged with -dirty suffix$(NC)"; \
		fi; \
	fi
	docker build -t $(IMAGE) -f operator/Dockerfile operator/
	@echo "$(GREEN)✅ Docker image built successfully: $(IMAGE)$(NC)"
	@echo ""
	@echo "$(BLUE)🧪 Testing Modal package import in the image...$(NC)"
	docker run --rm $(IMAGE) python -c "import modal; print('✓ Modal package imported successfully')"
	@echo "$(GREEN)🎉 Build and test completed!$(NC)"

deploy: build install ## Build and install the operator in one step

update-image: ## Update the image in deployment.yaml (used by install)
	@echo "$(BLUE)Updating deployment.yaml with image: $(IMAGE)$(NC)"
	@if [ -f manifests/deployment.yaml ]; then \
		cp manifests/deployment.yaml manifests/deployment.yaml.bak; \
		if grep -q "^[[:space:]]*image:[[:space:]]*" manifests/deployment.yaml; then \
			sed -i.bak "s|^\([[:space:]]*image:[[:space:]]*\).*|\1$(IMAGE)|g" manifests/deployment.yaml; \
			echo "$(GREEN)✅ Updated image in deployment.yaml$(NC)"; \
		else \
			echo "$(YELLOW)⚠ Warning: No image field found in deployment.yaml$(NC)"; \
		fi; \
		if grep -q "name: WATCH_NAMESPACE" manifests/deployment.yaml; then \
			if [ -n "$(WATCH_NAMESPACE)" ]; then \
				sed -i.bak "/name: WATCH_NAMESPACE/,/value:/ s|value:.*|value: '$(WATCH_NAMESPACE)'|" manifests/deployment.yaml; \
			else \
				sed -i.bak "/name: WATCH_NAMESPACE/,/value:/ s|value:.*|value: ''|" manifests/deployment.yaml; \
			fi; \
			echo "$(GREEN)✅ Updated WATCH_NAMESPACE in deployment.yaml$(NC)"; \
		fi; \
		rm -f manifests/deployment.yaml.bak; \
	else \
		echo "$(RED)✗ Error: manifests/deployment.yaml not found$(NC)"; \
		exit 1; \
	fi

install: update-image ## Install the operator (updates image, installs CRD and manifests)
	@echo "$(BLUE)Installing Modal GitOps Operator...$(NC)"
	@echo "$(BLUE)Image: $(IMAGE)$(NC)"
	@echo "$(BLUE)Namespace: $(NAMESPACE)$(NC)"
	@if [ -f .env ]; then \
		echo "$(GREEN)✓ Loaded secrets from .env file$(NC)"; \
	fi
	@echo ""
	
	@# Check prerequisites
	@if ! command -v kubectl > /dev/null; then \
		echo "$(RED)✗ Error: kubectl is required but not installed$(NC)"; \
		exit 1; \
	fi
	
	@if ! kubectl cluster-info > /dev/null 2>&1; then \
		echo "$(RED)✗ Error: Cannot access Kubernetes cluster$(NC)"; \
		exit 1; \
	fi
	@# Check if kind cluster and load image if needed
	@$(MAKE) load-kind
	
	@# Create namespace
	@echo "$(BLUE)Creating namespace $(NAMESPACE)...$(NC)"
	@kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	
	@# Install CRD
	@echo "$(BLUE)Installing ModalDeployment CRD...$(NC)"
	@kubectl apply -f crds/modaldeployment-crd.yaml
	@kubectl wait --for condition=established --timeout=60s crd/modaldeployments.modal.io || true
	
	@# Create Modal credentials secret if provided
	@if [ -n "$(MODAL_TOKEN_ID)" ] && [ -n "$(MODAL_TOKEN_SECRET)" ]; then \
		echo "$(BLUE)Creating Modal credentials secret...$(NC)"; \
		kubectl create secret generic modal-credentials \
			--namespace=$(NAMESPACE) \
			--from-literal=token-id=$(MODAL_TOKEN_ID) \
			--from-literal=token-secret=$(MODAL_TOKEN_SECRET) \
			--dry-run=client -o yaml | kubectl apply -f -; \
		echo "$(GREEN)✅ Modal credentials secret created$(NC)"; \
	else \
		echo "$(YELLOW)⚠ Warning: Modal credentials not provided$(NC)"; \
		echo "$(BLUE)   Create the secret manually with:$(NC)"; \
		echo "   kubectl create secret generic modal-credentials \\"; \
		echo "     --namespace=$(NAMESPACE) \\"; \
		echo "     --from-literal=token-id=YOUR_TOKEN_ID \\"; \
		echo "     --from-literal=token-secret=YOUR_TOKEN_SECRET"; \
	fi
	
	@# Install RBAC
	@echo "$(BLUE)Installing RBAC resources...$(NC)"
	@kubectl apply -f manifests/rbac.yaml
	
	@# Install operator deployment
	@echo "$(BLUE)Installing operator deployment...$(NC)"
	@kubectl apply -f manifests/deployment.yaml
	
	@# WATCH_NAMESPACE is already set in deployment.yaml by update-image target
	@if [ -z "$(WATCH_NAMESPACE)" ]; then \
		echo "$(BLUE)WATCH_NAMESPACE is empty - operator will watch all namespaces$(NC)"; \
	else \
		echo "$(BLUE)WATCH_NAMESPACE is set to: $(WATCH_NAMESPACE)$(NC)"; \
	fi
	
	@# Wait for operator to be ready
	@echo "$(BLUE)Waiting for operator to be ready...$(NC)"
	@kubectl wait --for=condition=available --timeout=300s deployment/modal-operator -n $(NAMESPACE) || true
	
	@# Verify installation
	@echo ""
	@echo "$(BLUE)Verifying installation...$(NC)"
	@kubectl get crd modaldeployments.modal.io > /dev/null 2>&1 && \
		echo "$(GREEN)✅ CRD installed$(NC)" || \
		echo "$(RED)✗ CRD missing$(NC)"
	@kubectl get deployment modal-operator -n $(NAMESPACE) > /dev/null 2>&1 && \
		echo "$(GREEN)✅ Operator deployment exists$(NC)" || \
		echo "$(RED)✗ Operator deployment missing$(NC)"
	@kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=modal-operator | grep -q Running && \
		echo "$(GREEN)✅ Operator pod is running$(NC)" || \
		echo "$(YELLOW)⚠ Operator pod is not running yet$(NC)"
	
	@echo ""
	@echo "$(GREEN)✅ Installation completed!$(NC)"
	@echo ""
	@echo "$(BLUE)Next steps:$(NC)"
	@echo "1. View operator logs: kubectl logs -n $(NAMESPACE) -l app.kubernetes.io/name=modal-operator -f"
	@echo "2. Deploy a sample: kubectl apply -f examples/function-deployment.yaml"
	@echo "3. Check deployments: kubectl get modaldeployments"

uninstall: ## Uninstall the operator
	@echo "$(BLUE)Uninstalling Modal GitOps Operator...$(NC)"
	@kubectl delete -f manifests/ --ignore-not-found=true
	@kubectl delete -f crds/ --ignore-not-found=true
	@kubectl delete namespace $(NAMESPACE) --ignore-not-found=true
	@echo "$(GREEN)✅ Modal operator uninstalled$(NC)"

test: ## Test the operator (build image and verify)
	@echo "$(BLUE)Running tests...$(NC)"
	@$(MAKE) build
	@echo "$(GREEN)✅ Tests passed$(NC)"

clean: ## Clean up generated files
	@echo "$(BLUE)Cleaning up...$(NC)"
	@if [ -f manifests/deployment.yaml.bak ]; then \
		mv manifests/deployment.yaml.bak manifests/deployment.yaml; \
		echo "$(GREEN)✅ Restored original deployment.yaml$(NC)"; \
	fi

lint: ## Run pre-commit hooks on all files (installs hooks automatically if not installed)
	@if command -v pre-commit > /dev/null 2>&1; then \
		if [ ! -f .git/hooks/pre-commit ]; then \
			echo "$(BLUE)Pre-commit hooks not installed, installing now...$(NC)"; \
			pre-commit install; \
			echo "$(GREEN)✅ Pre-commit hooks installed$(NC)"; \
		fi; \
		echo "$(BLUE)Running linters on all files...$(NC)"; \
		pre-commit run --all-files; \
	else \
		echo "$(RED)✗ Error: pre-commit is not installed$(NC)"; \
		echo "$(BLUE)   Install it with: pip install pre-commit$(NC)"; \
		exit 1; \
	fi

