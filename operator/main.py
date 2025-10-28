#!/usr/bin/env python3

import asyncio
import logging
import os
import sys
from typing import Dict, Any

import kopf
import modal
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from modal_controller import ModalController
from utils import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize Modal client
try:
    if os.getenv("MODAL_TOKEN_ID") and os.getenv("MODAL_TOKEN_SECRET"):
        # Modal client is initialized automatically when imported
        # We just need to ensure credentials are available
        import modal
        logger.info("Modal client initialized successfully")
        modal_client = None  # Will be initialized per-operation
    else:
        logger.error(
            "Modal credentials not found. Set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET environment variables"
        )
        sys.exit(1)
except Exception as e:
    logger.error(f"Failed to initialize Modal client: {e}")
    sys.exit(1)

# Initialize Kubernetes client
try:
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount"):
        config.load_incluster_config()
        logger.info("Loaded in-cluster Kubernetes config")
    else:
        config.load_kube_config()
        logger.info("Loaded local Kubernetes config")

    k8s_client = client.ApiClient()
    custom_objects_api = client.CustomObjectsApi(k8s_client)
    core_v1_api = client.CoreV1Api(k8s_client)
except Exception as e:
    logger.error(f"Failed to initialize Kubernetes client: {e}")
    sys.exit(1)

# Initialize controller
controller = ModalController(None, custom_objects_api, core_v1_api)


@kopf.on.create("modal.io", "v1", "modaldeployments")
async def create_modal_deployment(
    spec: Dict[str, Any], name: str, namespace: str, **kwargs
):
    """Handle creation of ModalDeployment resources"""
    logger.info(f"Creating ModalDeployment {namespace}/{name}")

    try:
        # Update status to Deploying
        await controller.update_status(
            name=name,
            namespace=namespace,
            phase="Deploying",
            conditions=[
                {
                    "type": "Deploying",
                    "status": "True",
                    "reason": "DeploymentStarted",
                    "message": "Starting Modal deployment",
                }
            ],
        )

        # Deploy to Modal
        result = await controller.deploy_to_modal(spec, name, namespace)

        # Update status to Ready
        await controller.update_status(
            name=name,
            namespace=namespace,
            phase="Ready",
            modal_app_id=result.get("app_id"),
            url=result.get("url"),
            conditions=[
                {
                    "type": "Ready",
                    "status": "True",
                    "reason": "DeploymentSuccessful",
                    "message": "Modal deployment completed successfully",
                }
            ],
        )

        logger.info(f"Successfully created ModalDeployment {namespace}/{name}")
        return {
            "message": "Deployment created successfully",
            "app_id": result.get("app_id"),
        }

    except Exception as e:
        logger.error(f"Failed to create ModalDeployment {namespace}/{name}: {e}")

        # Update status to Failed
        await controller.update_status(
            name=name,
            namespace=namespace,
            phase="Failed",
            conditions=[
                {
                    "type": "Failed",
                    "status": "True",
                    "reason": "DeploymentFailed",
                    "message": f"Modal deployment failed: {str(e)}",
                }
            ],
        )

        raise kopf.PermanentError(f"Deployment failed: {e}")


@kopf.on.update("modal.io", "v1", "modaldeployments")
async def update_modal_deployment(
    spec: Dict[str, Any], name: str, namespace: str, **kwargs
):
    """Handle updates to ModalDeployment resources"""
    logger.info(f"Updating ModalDeployment {namespace}/{name}")

    try:
        # Update status to Deploying
        await controller.update_status(
            name=name,
            namespace=namespace,
            phase="Deploying",
            conditions=[
                {
                    "type": "Deploying",
                    "status": "True",
                    "reason": "UpdateStarted",
                    "message": "Starting Modal deployment update",
                }
            ],
        )

        # Update deployment in Modal
        result = await controller.update_modal_deployment(spec, name, namespace)

        # Update status to Ready
        await controller.update_status(
            name=name,
            namespace=namespace,
            phase="Ready",
            modal_app_id=result.get("app_id"),
            url=result.get("url"),
            conditions=[
                {
                    "type": "Ready",
                    "status": "True",
                    "reason": "UpdateSuccessful",
                    "message": "Modal deployment updated successfully",
                }
            ],
        )

        logger.info(f"Successfully updated ModalDeployment {namespace}/{name}")
        return {
            "message": "Deployment updated successfully",
            "app_id": result.get("app_id"),
        }

    except Exception as e:
        logger.error(f"Failed to update ModalDeployment {namespace}/{name}: {e}")

        # Update status to Failed
        await controller.update_status(
            name=name,
            namespace=namespace,
            phase="Failed",
            conditions=[
                {
                    "type": "Failed",
                    "status": "True",
                    "reason": "UpdateFailed",
                    "message": f"Modal deployment update failed: {str(e)}",
                }
            ],
        )

        raise kopf.PermanentError(f"Update failed: {e}")


@kopf.on.delete("modal.io", "v1", "modaldeployments")
async def delete_modal_deployment(
    spec: Dict[str, Any], name: str, namespace: str, **kwargs
):
    """Handle deletion of ModalDeployment resources"""
    logger.info(f"Deleting ModalDeployment {namespace}/{name}")

    try:
        # Update status to Terminating
        await controller.update_status(
            name=name,
            namespace=namespace,
            phase="Terminating",
            conditions=[
                {
                    "type": "Terminating",
                    "status": "True",
                    "reason": "DeletionStarted",
                    "message": "Starting Modal deployment deletion",
                }
            ],
        )

        # Delete from Modal
        await controller.delete_from_modal(spec, name, namespace)

        logger.info(f"Successfully deleted ModalDeployment {namespace}/{name}")
        return {"message": "Deployment deleted successfully"}

    except Exception as e:
        logger.error(f"Failed to delete ModalDeployment {namespace}/{name}: {e}")
        raise kopf.PermanentError(f"Deletion failed: {e}")


@kopf.on.startup()
def startup(**kwargs):
    """Operator startup handler"""
    logger.info("Modal GitOps Operator starting up...")
    logger.info(f"Watching namespace: {os.getenv('WATCH_NAMESPACE', 'all namespaces')}")


@kopf.on.cleanup()
def cleanup(**kwargs):
    """Operator cleanup handler"""
    logger.info("Modal GitOps Operator shutting down...")


if __name__ == "__main__":
    # Set up kopf configuration
    kopf.configure(
        verbose=os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG",
        log_format=kopf.LogFormat.FULL,
    )

    # Run the operator
    kopf.run(
        clusterwide=os.getenv("WATCH_NAMESPACE") is None,
        namespace=os.getenv("WATCH_NAMESPACE"),
    )
