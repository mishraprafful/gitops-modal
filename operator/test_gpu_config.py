#!/usr/bin/env python3
"""
Test script to demonstrate GPU configuration passing to Modal apps
"""

import sys
import os

# Try to import from current directory first (for Docker build context)
try:
    from modal_controller import ModalController
except ImportError:
    # Fallback for local development
    sys.path.append("operator")
    from modal_controller import ModalController


def test_gpu_config_parsing():
    """Test that GPU configurations are properly parsed and included in Modal app script"""

    # Mock configuration with GPU settings (similar to our GPU example)
    config = {
        "app_name": "test-gpu-app",
        "compute": {
            "cpu": "1.0",
            "memory": "1Gi",
            "gpu": "A100",
            "gpu_count": 2,
            "timeout": 7200,
        },
        "webhooks": {"enabled": False},
        "environment": {},
    }

    # Create controller instance (we don't need real k8s clients for this test)
    controller = ModalController(None, None, None)

    # Create a temporary source path
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        source_file = os.path.join(temp_dir, "main.py")
        with open(source_file, "w") as f:
            f.write("# Test source file")

        # Generate the deploy script
        deploy_script = controller._create_deploy_script(
            source_file, config, "test-gpu-app"
        )

        # Read the generated script
        with open(deploy_script, "r") as f:
            script_content = f.read()

        print("Generated Modal App Script:")
        print("=" * 50)
        print(script_content)
        print("=" * 50)

        # Verify GPU configuration is included
        expected_gpu_config = "gpu=modal.gpu.A100(count=2)"
        if expected_gpu_config in script_content:
            print("✅ GPU configuration correctly included in Modal app!")
            print(f"   Found: {expected_gpu_config}")
        else:
            print("❌ GPU configuration NOT found in Modal app")

        # Verify other compute resources
        if "cpu=1.0" in script_content:
            print("✅ CPU configuration correctly included")
        else:
            print("❌ CPU configuration missing")

        if "memory=1024" in script_content:  # 1Gi = 1024Mi
            print("✅ Memory configuration correctly included")
        else:
            print("❌ Memory configuration missing")

        if "timeout=7200" in script_content:
            print("✅ Timeout configuration correctly included")
        else:
            print("❌ Timeout configuration missing")

        # Exit with error if any test failed
        if (
            expected_gpu_config not in script_content
            or "cpu=1.0" not in script_content
            or "memory=1024" not in script_content
            or "timeout=7200" not in script_content
        ):
            print("\n❌ Test failed: Some configurations are missing!")
            sys.exit(1)

        print("\n✅ All GPU configuration tests passed!")


if __name__ == "__main__":
    test_gpu_config_parsing()
