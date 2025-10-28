# Kustomization for Modal Operator

This directory contains Kustomize configurations for deploying the Modal operator in different environments.

## Usage

### Development Environment
```bash
kubectl apply -k overlays/development
```

### Production Environment  
```bash
kubectl apply -k overlays/production
```

### Custom Configuration
```bash
# Edit overlays/production/kustomization.yaml
kubectl apply -k overlays/production
```
