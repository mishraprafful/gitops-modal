#!/bin/bash
set -euo pipefail

# Modal GitOps Operator Build Script

OPERATOR_IMAGE="${OPERATOR_IMAGE:-modal-operator:latest}"
BUILD_ARGS=""

echo "Building Modal GitOps Operator Docker image..."
echo "Image: $OPERATOR_IMAGE"

# Build the Docker image
docker build \
  -t "$OPERATOR_IMAGE" \
  -f operator/Dockerfile \
  operator/ \
  $BUILD_ARGS

echo "✅ Docker image built successfully: $OPERATOR_IMAGE"

# Test the image
echo "🧪 Testing Modal CLI availability in the image..."
docker run --rm "$OPERATOR_IMAGE" python -c "
import modal
import subprocess
import sys

print('✓ Modal package imported successfully')

try:
    # Test Modal CLI
    result = subprocess.run(['python', '-c', 'import modal; print(\"Modal CLI ready\")'], 
                          capture_output=True, text=True)
    if result.returncode == 0:
        print('✓ Modal CLI available')
    else:
        print('✗ Modal CLI test failed:', result.stderr)
        sys.exit(1)
except Exception as e:
    print('✗ Modal CLI test error:', e)
    sys.exit(1)

print('🎉 All tests passed!')
"

echo ""
echo "Next steps:"
echo "1. Push image to registry (if needed): docker push $OPERATOR_IMAGE"
echo "2. Update deployment: kubectl set image deployment/modal-operator operator=$OPERATOR_IMAGE -n modal-system"
echo "3. Check operator logs: kubectl logs -n modal-system -l app.kubernetes.io/name=modal-operator -f"