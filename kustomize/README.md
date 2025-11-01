# Kustomization for Modal Operator

This directory contains Kustomize overlays for deploying the Modal operator in different environments.

## Structure

- `../manifests/kustomization.yaml` - Base kustomization with common resources
- `overlays/development/` - Development environment overlay
- `overlays/production/` - Production environment overlay

## Usage

### Base Installation (using manifests directly)

```bash
# Install from base manifests
kubectl apply -k manifests/
```

### Development Environment

```bash
# Install with development overrides (lower resources, DEBUG logging)
kubectl apply -k overlays/development
```

### Production Environment  

```bash
# Install with production overrides (HA, higher resources, INFO logging)
kubectl apply -k overlays/production
```

### Custom Configuration

```bash
# Create your own overlay
mkdir -p overlays/my-env
# Edit overlays/my-env/kustomization.yaml to reference base and add patches
kubectl apply -k overlays/my-env
```

## Overlaying Image Names

To use a custom image in an overlay:

```yaml
# overlays/my-env/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../manifests

images:
  - name: modal-operator
    newName: my-registry.io/modal-operator
    newTag: v1.0.0
```
