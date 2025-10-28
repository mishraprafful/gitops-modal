import logging
import os
import sys
from datetime import datetime


def setup_logging():
    """Set up logging configuration for the operator"""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "json")

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


def parse_resource_requests(compute_spec):
    """Parse compute resource specifications"""
    resources = {}

    if "cpu" in compute_spec:
        cpu = compute_spec["cpu"]
        if isinstance(cpu, str):
            # Convert string CPU values to numbers
            if "." in cpu:
                resources["cpu"] = float(cpu)
            else:
                resources["cpu"] = int(cpu)
        else:
            resources["cpu"] = cpu

    if "memory" in compute_spec:
        memory = compute_spec["memory"]
        if isinstance(memory, str):
            # Parse memory strings like '512Mi', '2Gi'
            if memory.endswith("Mi"):
                resources["memory_mb"] = int(memory[:-2])
            elif memory.endswith("Gi"):
                resources["memory_mb"] = int(memory[:-2]) * 1024
            elif memory.endswith("Ti"):
                resources["memory_mb"] = int(memory[:-2]) * 1024 * 1024
        else:
            resources["memory_mb"] = memory

    return resources


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


def is_valid_cron_expression(cron_expr):
    """Validate cron expression"""
    try:
        from croniter import croniter

        croniter(cron_expr)
        return True
    except:
        return False


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
