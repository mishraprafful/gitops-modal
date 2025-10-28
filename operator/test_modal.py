#!/usr/bin/env python3
"""
Simple test script to check Modal API usage
"""
import os
import sys

def main():
    # Check if Modal credentials are available
    modal_token_id = os.getenv('MODAL_TOKEN_ID')
    modal_token_secret = os.getenv('MODAL_TOKEN_SECRET')

    print(f"MODAL_TOKEN_ID: {'***' if modal_token_id else 'Not set'}")
    print(f"MODAL_TOKEN_SECRET: {'***' if modal_token_secret else 'Not set'}")

    if not modal_token_id or not modal_token_secret:
        print("Warning: Modal credentials not found in environment")
        print("This is expected for testing the import")

    try:
        import modal
        print("✓ Modal package imported successfully")
        
        # Test basic Modal usage
        if hasattr(modal, '__version__'):
            print(f"✓ Modal version: {modal.__version__}")
        
        # Test app creation (this should work even without credentials)
        app = modal.App("test-app")
        print("✓ Modal App created successfully")
        print(f"  App name: {app.name if hasattr(app, 'name') else 'Unknown'}")
        
        print("\n✓ Modal API test successful!")
        
    except ImportError as e:
        print(f"✗ Error importing Modal: {e}")
        print("Install with: pip install modal")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error with Modal API: {e}")
        print(f"Error type: {type(e).__name__}")
        sys.exit(1)

if __name__ == "__main__":
    main()