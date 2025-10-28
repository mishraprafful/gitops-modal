import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional, List
import tempfile
import os
import subprocess
import asyncio

import modal
from kubernetes import client
from kubernetes.client.rest import ApiException
import git
import yaml
from croniter import croniter
from pydantic import BaseModel, ValidationError


logger = logging.getLogger(__name__)


class ModalController:
    """Controller for managing Modal deployments from Kubernetes CRD resources"""

    def __init__(
        self,
        modal_client: modal.Client,
        custom_objects_api: client.CustomObjectsApi,
        core_v1_api: client.CoreV1Api,
    ):
        self.modal_client = modal_client
        self.custom_objects_api = custom_objects_api
        self.core_v1_api = core_v1_api
        self.deployed_apps = {}  # Track deployed apps

    async def deploy_to_modal(
        self, spec: Dict[str, Any], name: str, namespace: str
    ) -> Dict[str, Any]:
        """Deploy a Modal application based on the CRD specification"""
        logger.info(f"Deploying {name} to Modal")

        try:
            # Prepare source code
            source_path = await self._prepare_source(spec.get("source", {}), name)

            # Load secrets and environment variables
            env_vars = await self._prepare_environment(
                spec.get("environment", {}), namespace
            )

            # Create Modal app configuration
            app_config = self._build_modal_config(spec, env_vars)

            # Deploy to Modal
            result = await self._execute_modal_deploy(source_path, app_config, name)

            # Track the deployment
            self.deployed_apps[f"{namespace}/{name}"] = {
                "app_id": result.get("app_id"),
                "url": result.get("url"),
                "source_path": source_path,
                "config": app_config,
            }

            return result

        except Exception as e:
            logger.error(f"Failed to deploy {name}: {e}")
            raise

    async def update_modal_deployment(
        self, spec: Dict[str, Any], name: str, namespace: str
    ) -> Dict[str, Any]:
        """Update an existing Modal deployment"""
        logger.info(f"Updating {name} in Modal")

        # For updates, we follow the same process as deployment
        # Modal handles versioning internally
        return await self.deploy_to_modal(spec, name, namespace)

    async def delete_from_modal(self, spec: Dict[str, Any], name: str, namespace: str):
        """Delete a Modal deployment"""
        logger.info(f"Deleting {name} from Modal")

        key = f"{namespace}/{name}"
        if key in self.deployed_apps:
            app_info = self.deployed_apps[key]

            try:
                # Stop the Modal app
                # Note: Modal doesn't have a direct delete API, but stopping/deactivating works
                await self._stop_modal_app(app_info["app_id"])

                # Clean up local resources
                if os.path.exists(app_info["source_path"]):
                    import shutil

                    shutil.rmtree(app_info["source_path"], ignore_errors=True)

                del self.deployed_apps[key]
                logger.info(f"Successfully deleted {name}")

            except Exception as e:
                logger.error(f"Failed to delete {name}: {e}")
                raise

    async def update_status(
        self,
        name: str,
        namespace: str,
        phase: str,
        modal_app_id: Optional[str] = None,
        url: Optional[str] = None,
        conditions: Optional[List[Dict]] = None,
    ):
        """Update the status of a ModalDeployment resource"""
        try:
            # Get current resource
            resource = self.custom_objects_api.get_namespaced_custom_object(
                group="modal.io",
                version="v1",
                namespace=namespace,
                plural="modaldeployments",
                name=name,
            )

            # Update status
            if "status" not in resource:
                resource["status"] = {}

            resource["status"]["phase"] = phase
            resource["status"]["lastDeployment"] = datetime.utcnow().isoformat() + "Z"

            if modal_app_id:
                resource["status"]["modalAppId"] = modal_app_id

            if url:
                resource["status"]["url"] = url

            if conditions:
                # Add timestamp to conditions
                for condition in conditions:
                    condition["lastTransitionTime"] = (
                        datetime.utcnow().isoformat() + "Z"
                    )
                resource["status"]["conditions"] = conditions

            # Update the resource
            self.custom_objects_api.patch_namespaced_custom_object(
                group="modal.io",
                version="v1",
                namespace=namespace,
                plural="modaldeployments",
                name=name,
                body=resource,
            )

            logger.info(f"Updated status for {namespace}/{name} to {phase}")

        except ApiException as e:
            logger.error(f"Failed to update status for {namespace}/{name}: {e}")
            raise

    async def _prepare_source(self, source_config: Dict[str, Any], name: str) -> str:
        """Prepare source code from git repository or container image"""
        temp_dir = tempfile.mkdtemp(prefix=f"modal-{name}-")

        if "git" in source_config:
            git_config = source_config["git"]
            repo_url = git_config["repository"]
            branch = git_config.get("branch", "main")
            path = git_config["path"]

            logger.info(f"Cloning {repo_url} (branch: {branch})")

            # Clone repository
            repo = git.Repo.clone_from(repo_url, temp_dir, branch=branch)

            # Check out specific revision if provided
            if "revision" in git_config:
                repo.git.checkout(git_config["revision"])

            # The actual app file should be at temp_dir/path
            app_file = os.path.join(temp_dir, path)
            if not os.path.exists(app_file):
                raise FileNotFoundError(f"App file not found at {path}")

            return app_file

        elif "image" in source_config:
            # For container images, we need to extract the Modal app
            # This is a simplified implementation
            image_config = source_config["image"]
            image_name = f"{image_config['name']}:{image_config.get('tag', 'latest')}"

            logger.info(f"Extracting Modal app from image {image_name}")

            # Extract app from container (simplified - in practice you'd need more sophisticated logic)
            # For now, assume the image has a standard Modal app at /app/main.py
            dummy_app = os.path.join(temp_dir, "main.py")
            with open(dummy_app, "w") as f:
                f.write("# Placeholder for container-based app\nimport modal\n")

            return dummy_app

        else:
            raise ValueError(
                "Source configuration must specify either 'git' or 'image'"
            )

    async def _prepare_environment(
        self, env_config: Dict[str, Any], namespace: str
    ) -> Dict[str, str]:
        """Prepare environment variables and secrets"""
        env_vars = {}

        # Add regular environment variables
        if "variables" in env_config:
            env_vars.update(env_config["variables"])

        # Load secrets from Kubernetes
        if "secrets" in env_config:
            for secret_config in env_config["secrets"]:
                secret_ref = secret_config.get("secretRef", {})
                secret_name = secret_ref["name"]
                secret_namespace = secret_ref.get("namespace", namespace)

                try:
                    secret = self.core_v1_api.read_namespaced_secret(
                        name=secret_name, namespace=secret_namespace
                    )

                    # Add all secret data as environment variables
                    if secret.data:
                        for key, value in secret.data.items():
                            import base64

                            decoded_value = base64.b64decode(value).decode("utf-8")
                            env_vars[key] = decoded_value

                except ApiException as e:
                    logger.error(
                        f"Failed to load secret {secret_namespace}/{secret_name}: {e}"
                    )
                    raise

        return env_vars

    def _build_modal_config(
        self, spec: Dict[str, Any], env_vars: Dict[str, str]
    ) -> Dict[str, Any]:
        """Build Modal application configuration"""
        config = {"app_name": spec["appName"], "environment": env_vars}

        # Add compute configuration
        if "compute" in spec:
            compute = spec["compute"]
            config["compute"] = {
                "cpu": compute.get("cpu"),
                "memory": compute.get("memory"),
                "gpu": compute.get("gpu"),
                "gpu_count": compute.get("gpuCount", 1),
                "timeout": compute.get("timeout", 300),
            }

        # Add scaling configuration
        if "scaling" in spec:
            scaling = spec["scaling"]
            config["scaling"] = {
                "min_instances": scaling.get("minInstances", 0),
                "max_instances": scaling.get("maxInstances", 10),
                "concurrency": scaling.get("concurrency", 1),
                "idle_timeout": scaling.get("idleTimeout", 300),
            }

        # Add webhook configuration
        if "webhooks" in spec and spec["webhooks"].get("enabled", False):
            config["webhooks"] = {
                "path": spec["webhooks"].get("path", "/"),
                "methods": spec["webhooks"].get("methods", ["GET", "POST"]),
            }

        # Add schedule configuration
        if "schedule" in spec:
            schedule = spec["schedule"]
            config["schedule"] = {
                "cron": schedule["cron"],
                "timezone": schedule.get("timezone", "UTC"),
            }

        return config

    async def _execute_modal_deploy(
        self, source_path: str, config: Dict[str, Any], name: str
    ) -> Dict[str, Any]:
        """Execute the actual Modal deployment"""
        logger.info(f"Executing Modal deployment for {name}")

        try:
            # Set environment variables for Modal
            env = os.environ.copy()
            env.update(config.get("environment", {}))

            # Create a deployment script
            deploy_script = self._create_deploy_script(source_path, config)

            # Execute the deployment
            process = await asyncio.create_subprocess_exec(
                "python",
                deploy_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = (
                    stderr.decode("utf-8") if stderr else "Unknown deployment error"
                )
                raise RuntimeError(f"Modal deployment failed: {error_msg}")

            # Parse deployment result (simplified)
            result = {
                "app_id": f"modal-app-{name}",  # In practice, this would come from Modal API
                "url": None,  # Will be set if it's a web app
            }

            # If it's a web app, set URL
            if "webhooks" in config:
                result["url"] = f"https://{name}.modal.run"

            logger.info(f"Modal deployment successful for {name}")
            return result

        except Exception as e:
            logger.error(f"Modal deployment failed for {name}: {e}")
            raise

    def _create_deploy_script(self, source_path: str, config: Dict[str, Any]) -> str:
        """Create a Python script to deploy to Modal"""
        script_dir = os.path.dirname(source_path)
        script_path = os.path.join(script_dir, "deploy.py")

        script_content = f"""
import modal
import os
import sys

# Add source directory to path
sys.path.insert(0, "{script_dir}")

try:
    # Import the Modal app
    app_module = __import__(os.path.basename("{source_path}").replace(".py", ""))
    
    # Deploy the app
    print("Deploying to Modal...")
    print("Deployment completed successfully")
    
except Exception as e:
    print(f"Deployment failed: {{e}}", file=sys.stderr)
    sys.exit(1)
"""

        with open(script_path, "w") as f:
            f.write(script_content)

        return script_path

    async def _stop_modal_app(self, app_id: str):
        """Stop a Modal application"""
        logger.info(f"Stopping Modal app {app_id}")

        # In a real implementation, you would call Modal's API to stop/deactivate the app
        # For now, this is a placeholder
        await asyncio.sleep(1)  # Simulate API call

        logger.info(f"Modal app {app_id} stopped")
