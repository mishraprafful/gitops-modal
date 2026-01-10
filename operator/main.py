#!/usr/bin/env python3

import logging
import os
import sys
from typing import Dict, Any

import kopf
from kubernetes import client, config

from modal_controller import ModalController
from utils import setup_logging
from health_server import start_health_server, set_ready, stop_health_server

# Fix for getpass.getuser() when running in container without proper /etc/passwd entry
if not os.environ.get("USER"):
    os.environ["USER"] = "operator"

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# Start health check server early (before initialization)
# This allows /healthz to work immediately, /readyz will return 503 until ready
health_thread = None
health_server = None
try:
    health_thread, health_server = start_health_server(host="0.0.0.0", port=8081)
except Exception as e:
    logger.error(f"Failed to start health check server: {e}")
    # Continue anyway - health checks will fail but operator might still work

# Initialize Modal client
try:
    if os.getenv("MODAL_TOKEN_ID") and os.getenv("MODAL_TOKEN_SECRET"):
        # Modal client is initialized automatically when imported
        # We just need to ensure credentials are available

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

# Mark operator as ready now that all initialization is complete
set_ready()
logger.info("Operator initialization complete - ready to handle requests")


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
                    "type": "Reconciling",
                    "status": "True",
                    "reason": "DeploymentStarted",
                    "message": "Starting Modal deployment",
                },
                {
                    "type": "Ready",
                    "status": "False",
                    "reason": "Deploying",
                    "message": "Deployment in progress",
                },
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
                    "type": "Reconciling",
                    "status": "False",
                    "reason": "DeploymentSuccessful",
                    "message": "Deployment completed",
                },
                {
                    "type": "Ready",
                    "status": "True",
                    "reason": "DeploymentSuccessful",
                    "message": "Modal deployment completed successfully",
                },
                {
                    "type": "Available",
                    "status": "True",
                    "reason": "DeploymentSuccessful",
                    "message": "Modal app is deployed and available",
                },
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
                    "type": "Reconciling",
                    "status": "False",
                    "reason": "DeploymentFailed",
                    "message": "Deployment attempt completed with failure",
                },
                {
                    "type": "Ready",
                    "status": "False",
                    "reason": "DeploymentFailed",
                    "message": f"Modal deployment failed: {str(e)}",
                },
                {
                    "type": "Stalled",
                    "status": "True",
                    "reason": "DeploymentFailed",
                    "message": f"Modal deployment failed: {str(e)}",
                },
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
                    "type": "Reconciling",
                    "status": "True",
                    "reason": "UpdateStarted",
                    "message": "Starting Modal deployment update",
                },
                {
                    "type": "Ready",
                    "status": "False",
                    "reason": "Updating",
                    "message": "Update in progress",
                },
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
                    "type": "Reconciling",
                    "status": "False",
                    "reason": "UpdateSuccessful",
                    "message": "Update completed",
                },
                {
                    "type": "Ready",
                    "status": "True",
                    "reason": "UpdateSuccessful",
                    "message": "Modal deployment updated successfully",
                },
                {
                    "type": "Available",
                    "status": "True",
                    "reason": "UpdateSuccessful",
                    "message": "Modal app is deployed and available",
                },
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
                    "type": "Reconciling",
                    "status": "False",
                    "reason": "UpdateFailed",
                    "message": "Update attempt completed with failure",
                },
                {
                    "type": "Ready",
                    "status": "False",
                    "reason": "UpdateFailed",
                    "message": f"Modal deployment update failed: {str(e)}",
                },
                {
                    "type": "Stalled",
                    "status": "True",
                    "reason": "UpdateFailed",
                    "message": f"Modal deployment update failed: {str(e)}",
                },
            ],
        )

        raise kopf.PermanentError(f"Update failed: {e}")


@kopf.on.delete("modal.io", "v1", "modaldeployments")
async def delete_modal_deployment(
    spec: Dict[str, Any], name: str, namespace: str, **kwargs
):
    """Handle deletion of ModalDeployment resources"""
    logger.info(f"Deleting ModalDeployment {namespace}/{name}")

    # Try to update status to Terminating, but don't fail if it doesn't work
    # (resource may already be deleted or in deletion process)
    try:
        await controller.update_status(
            name=name,
            namespace=namespace,
            phase="Terminating",
            conditions=[
                {
                    "type": "Reconciling",
                    "status": "True",
                    "reason": "DeletionStarted",
                    "message": "Starting Modal deployment deletion",
                },
                {
                    "type": "Ready",
                    "status": "False",
                    "reason": "Terminating",
                    "message": "Resource is being deleted",
                },
            ],
        )
    except Exception as status_error:
        # Status update may fail if resource is already being deleted
        logger.warning(
            f"Failed to update status to Terminating for {namespace}/{name}: {status_error}"
        )
        logger.info("Continuing with Modal app deletion despite status update failure")

    # Delete from Modal - this should always proceed even if status update failed
    try:
        await controller.delete_from_modal(spec, name, namespace)
        logger.info(f"Successfully deleted ModalDeployment {namespace}/{name}")
        return {"message": "Deployment deleted successfully"}
    except Exception as e:
        # Log error but don't raise PermanentError - allow deletion to complete
        # The Modal app deletion may have failed, but we shouldn't block K8s resource deletion
        logger.error(f"Error during Modal app deletion for {namespace}/{name}: {e}")
        logger.warning("Continuing with resource deletion despite Modal cleanup error")
        return {"message": "Deployment deletion completed with warnings"}


@kopf.on.timer("modal.io", "v1", "modaldeployments", interval=120.0)
async def monitor_modal_health(
    spec: Dict[str, Any], name: str, namespace: str, status: Dict[str, Any], **kwargs
):
    """Check Modal app health every 120 seconds"""
    logger.info(f"Health check for {namespace}/{name}")

    # Skip if not yet deployed or already failed/terminating
    current_phase = status.get("phase") if status else None
    if not current_phase or current_phase not in ["Ready", "Deploying"]:
        logger.debug(
            f"Skipping health check for {namespace}/{name} - phase is {current_phase}"
        )
        return

    modal_app_id = status.get("modalAppId") if status else None
    app_name = spec.get("appName", name)

    # Check if app exists in Modal
    is_healthy = await controller.check_app_health(modal_app_id, app_name)

    if is_healthy:
        # Only update if status needs to change
        if current_phase != "Ready":
            await controller.update_status(
                name=name,
                namespace=namespace,
                phase="Ready",
                conditions=[
                    {
                        "type": "Available",
                        "status": "True",
                        "reason": "AppHealthy",
                        "message": "Modal app is deployed and available",
                    },
                    {
                        "type": "Ready",
                        "status": "True",
                        "reason": "Reconciled",
                        "message": "Resource reconciled successfully",
                    },
                    {
                        "type": "Stalled",
                        "status": "False",
                        "reason": "AppHealthy",
                        "message": "App is healthy",
                    },
                ],
            )
        logger.debug(f"Health check passed for {namespace}/{name}")
    else:
        logger.warning(
            f"Health check failed for {namespace}/{name} - app not found in Modal"
        )
        await controller.update_status(
            name=name,
            namespace=namespace,
            phase="Failed",
            conditions=[
                {
                    "type": "Available",
                    "status": "False",
                    "reason": "AppNotFound",
                    "message": f"Modal app {app_name} not found in deployed apps",
                },
                {
                    "type": "Ready",
                    "status": "False",
                    "reason": "AppMissing",
                    "message": "App may have been deleted outside of operator",
                },
                {
                    "type": "Stalled",
                    "status": "True",
                    "reason": "AppMissing",
                    "message": "App may have been deleted outside of operator",
                },
            ],
        )


@kopf.on.startup()
def startup(**kwargs):
    """Operator startup handler"""
    logger.info("Modal GitOps Operator starting up...")
    watch_namespace = os.getenv("WATCH_NAMESPACE", "")
    if watch_namespace:
        logger.info(f"Watching namespace: {watch_namespace}")
    else:
        logger.info("Watching all namespaces")


@kopf.on.cleanup()
def cleanup(**kwargs):
    """Operator cleanup handler"""
    logger.info("Modal GitOps Operator shutting down...")
    # Stop health check server gracefully
    if health_server:
        stop_health_server(health_server)


if __name__ == "__main__":
    # Set up kopf configuration
    kopf.configure(
        verbose=os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG",
        log_format=kopf.LogFormat.FULL,
    )

    # Run the operator
    # If WATCH_NAMESPACE is empty or None, watch all namespaces (clusterwide)
    watch_namespace = os.getenv("WATCH_NAMESPACE") or None
    if watch_namespace:
        # Watch specific namespace
        kopf.run(namespace=watch_namespace)
    else:
        # Watch all namespaces (clusterwide)
        kopf.run(clusterwide=True)
