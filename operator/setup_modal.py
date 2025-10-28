#!/usr/bin/env python3
"""
Modal CLI setup script for the GitOps operator
This script ensures Modal CLI is properly configured with credentials
"""
import os
import sys
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_modal_auth():
    """Set up Modal authentication using environment variables"""
    token_id = os.getenv('MODAL_TOKEN_ID')
    token_secret = os.getenv('MODAL_TOKEN_SECRET')
    
    if not token_id or not token_secret:
        logger.error("MODAL_TOKEN_ID and MODAL_TOKEN_SECRET environment variables are required")
        return False
    
    # Create Modal config directory
    config_path = Path(os.getenv('MODAL_CONFIG_PATH', '/home/operator/.modal'))
    config_path.mkdir(parents=True, exist_ok=True)
    
    # Create Modal token config file
    token_config = {
        "token_id": token_id,
        "token_secret": token_secret
    }
    
    token_file = config_path / "token"
    with open(token_file, 'w') as f:
        json.dump(token_config, f)
    
    # Set proper permissions
    token_file.chmod(0o600)
    
    logger.info(f"Modal authentication configured at {token_file}")
    return True


def test_modal_import():
    """Test that Modal can be imported and basic functionality works"""
    try:
        import modal
        logger.info("✓ Modal package imported successfully")
        
        # Test creating a basic app (this should work without authentication)
        app = modal.App("test-app")
        logger.info(f"✓ Created test app: {app.name}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Modal import/basic test failed: {e}")
        return False


def main():
    """Main setup function"""
    logger.info("Setting up Modal GitOps Operator environment...")
    
    # Test Modal import first
    if not test_modal_import():
        sys.exit(1)
    
    # Set up authentication
    if not setup_modal_auth():
        sys.exit(1)
    
    logger.info("🎉 Modal GitOps Operator environment ready!")
    return True


if __name__ == "__main__":
    main()