import logging
import os
import sys
from datetime import datetime


def setup_logging():
    """Set up logging configuration for the operator"""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Set specific logger levels
    logging.getLogger("kubernetes").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {log_level}")


def validate_modal_credentials():
    """Validate that Modal credentials are available"""
    token_id = os.getenv("MODAL_TOKEN_ID")
    token_secret = os.getenv("MODAL_TOKEN_SECRET")

    if not token_id or not token_secret:
        raise ValueError(
            "Modal credentials not found. Set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET"
        )

    return True


def sanitize_app_name(name):
    """Sanitize application name for Modal"""
    # Modal app names should be DNS-compatible
    sanitized = name.lower()
    sanitized = "".join(c if c.isalnum() or c in "-" else "-" for c in sanitized)
    sanitized = sanitized.strip("-")

    # Ensure it starts and ends with alphanumeric
    while sanitized.startswith("-"):
        sanitized = sanitized[1:]
    while sanitized.endswith("-"):
        sanitized = sanitized[:-1]

    return sanitized


def create_condition(condition_type, status, reason, message):
    """Create a Kubernetes condition object"""
    return {
        "type": condition_type,
        "status": status,
        "reason": reason,
        "message": message,
        "lastTransitionTime": datetime.utcnow().isoformat() + "Z",
    }


def merge_environment_variables(*env_dicts):
    """Merge multiple environment variable dictionaries"""
    merged = {}
    for env_dict in env_dicts:
        if env_dict:
            merged.update(env_dict)
    return merged


class OperatorError(Exception):
    """Base exception for operator errors"""

    pass


class DeploymentError(OperatorError):
    """Exception raised during deployment operations"""

    pass


class ValidationError(OperatorError):
    """Exception raised during validation"""

    pass
