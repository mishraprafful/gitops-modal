import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import tempfile
import os
import asyncio

import modal
from kubernetes import client
from kubernetes.client.rest import ApiException
import git


logger = logging.getLogger(__name__)


class ModalController:
    """Controller for managing Modal deployments from Kubernetes CRD resources"""

    def __init__(
        self,
        modal_client: Optional[modal.Client],
        custom_objects_api: client.CustomObjectsApi,
        core_v1_api: client.CoreV1Api,
    ):
        self.modal_client = modal_client  # Can be None, will use modal directly
        self.custom_objects_api = custom_objects_api
        self.core_v1_api = core_v1_api
        self.deployed_apps: Dict[str, Dict[str, Any]] = {}  # Track deployed apps

    async def deploy_to_modal(
        self, spec: Dict[str, Any], name: str, namespace: str
    ) -> Dict[str, Any]:
        """Deploy a Modal application based on the CRD specification"""
        logger.info(f"Deploying {name} to Modal")

        try:
            # Prepare source code
            source_path = await self._prepare_source(
                spec.get("source", {}), name, namespace
            )

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
        """Delete a Modal deployment using the app ID"""
        logger.info(f"Deleting {name} from Modal")

        modal_app_id = None
        source_path = None

        try:
            # Strategy 1: Get app ID from CRD status (if it was stored)
            try:
                resource = self.custom_objects_api.get_namespaced_custom_object(
                    group="modal.io",
                    version="v1",
                    namespace=namespace,
                    plural="modaldeployments",
                    name=name,
                )
                if resource.get("status", {}).get("modalAppId"):
                    modal_app_id = resource["status"]["modalAppId"]
                    logger.info(f"Found Modal app ID from CRD status: {modal_app_id}")
            except ApiException as e:
                if e.status == 404:
                    logger.warning(
                        f"Resource {namespace}/{name} not found, may already be deleted"
                    )
                else:
                    logger.warning(f"Failed to retrieve CRD status: {e}")

            # Strategy 2: Fall back to in-memory tracking if available
            key = f"{namespace}/{name}"
            if not modal_app_id:
                if key in self.deployed_apps:
                    app_info = self.deployed_apps[key]
                    modal_app_id = app_info.get("app_id")
                    source_path = app_info.get("source_path")
                    logger.info(
                        f"Found Modal app ID from in-memory tracking: {modal_app_id}"
                    )

            # Strategy 3: Query Modal to find the app by name (last resort)
            if not modal_app_id:
                logger.info(
                    "No stored app ID found, querying Modal API to find the app..."
                )

                # Determine the app name to search for
                app_name_to_find = spec.get("appName", name)

                # Try to get the actual app name from source file if available
                if key in self.deployed_apps:
                    source_path = self.deployed_apps[key].get("source_path")

                if source_path and os.path.exists(source_path):
                    try:
                        extracted_name = self._extract_app_name_from_source(source_path)
                        if extracted_name:
                            app_name_to_find = extracted_name
                            logger.info(
                                f"Using extracted app name for search: {extracted_name}"
                            )
                    except Exception as e:
                        logger.debug(f"Could not extract app name from source: {e}")

                # Use the helper method to find app ID by name
                modal_app_id = await self._get_app_id_by_name(app_name_to_find)

                if modal_app_id:
                    logger.info(
                        f"Found app ID from Modal API: {modal_app_id} "
                        f"(app name: {app_name_to_find})"
                    )

            # Execute deletion if we have an app ID
            if not modal_app_id:
                logger.warning(
                    f"No app ID found for {namespace}/{name} (searched for app name: {app_name_to_find if 'app_name_to_find' in locals() else 'N/A'}). "
                    "App may have never been deployed successfully or was already deleted."
                )
            else:
                logger.info(f"Deleting Modal app with ID: {modal_app_id}")
                await self._stop_modal_app(modal_app_id)

            # Clean up local resources
            if not source_path and key in self.deployed_apps:
                source_path = self.deployed_apps[key].get("source_path")

            if source_path and os.path.exists(source_path):
                import shutil

                shutil.rmtree(source_path, ignore_errors=True)
                logger.info(f"Cleaned up local resources at {source_path}")

            # Remove from in-memory tracking
            if key in self.deployed_apps:
                del self.deployed_apps[key]

            logger.info(f"Successfully deleted {name} from Modal")

        except Exception as e:
            logger.error(f"Failed to delete {name}: {e}")
            # Don't raise - allow deletion to proceed even if Modal cleanup fails
            logger.warning("Continuing with deletion despite Modal cleanup error")

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
            resource["status"]["lastDeployment"] = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )

            if modal_app_id:
                resource["status"]["modalAppId"] = modal_app_id

            if url:
                resource["status"]["url"] = url

            if conditions:
                # Add timestamp to conditions
                for condition in conditions:
                    condition["lastTransitionTime"] = (
                        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
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

    async def _prepare_source(
        self, source_config: Dict[str, Any], name: str, namespace: str
    ) -> str:
        """Prepare source code from git repository or container image"""
        temp_dir = tempfile.mkdtemp(prefix=f"modal-{name}-")

        if "git" in source_config:
            git_config = source_config["git"]
            repo_url = git_config["repository"]
            branch = git_config.get("branch", "main")
            path = git_config["path"]

            logger.info(f"Cloning {repo_url} (branch: {branch})")

            # Handle credentials for private repositories
            git_env = None
            ssh_key_file = None
            authenticated_url = repo_url

            if "credentials" in git_config:
                credentials_config = git_config["credentials"]
                if "secretRef" in credentials_config:
                    secret_ref = credentials_config["secretRef"]
                    secret_name = secret_ref["name"]
                    secret_namespace = secret_ref.get("namespace", namespace)

                    try:
                        secret = self.core_v1_api.read_namespaced_secret(
                            name=secret_name, namespace=secret_namespace
                        )

                        import base64

                        # Check for SSH private key
                        if secret.data and "ssh-privatekey" in secret.data:
                            logger.info("Using SSH key authentication")
                            ssh_key_content = base64.b64decode(
                                secret.data["ssh-privatekey"]
                            ).decode("utf-8")

                            # Write SSH key to temporary file
                            ssh_key_file = tempfile.NamedTemporaryFile(
                                mode="w", delete=False, suffix="_ssh_key"
                            )
                            ssh_key_file.write(ssh_key_content)
                            ssh_key_file.close()
                            os.chmod(ssh_key_file.name, 0o600)

                            # Set up GIT_SSH_COMMAND to use the key
                            git_ssh_cmd = f"ssh -i {ssh_key_file.name} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
                            git_env = {"GIT_SSH_COMMAND": git_ssh_cmd}

                        # Check for Personal Access Token
                        elif secret.data and "token" in secret.data:
                            logger.info("Using Personal Access Token authentication")
                            token = base64.b64decode(secret.data["token"]).decode(
                                "utf-8"
                            )

                            # Inject token into HTTPS URL
                            # Handle both https://github.com/user/repo and https://user@github.com/user/repo formats
                            if repo_url.startswith("https://"):
                                # Extract domain and path
                                url_parts = repo_url.replace("https://", "").split(
                                    "/", 1
                                )
                                if len(url_parts) == 2:
                                    domain = url_parts[0]
                                    repo_path = url_parts[1]
                                    # Remove existing credentials if present
                                    if "@" in domain:
                                        domain = domain.split("@")[1]
                                    authenticated_url = (
                                        f"https://oauth2:{token}@{domain}/{repo_path}"
                                    )
                                else:
                                    logger.warning(
                                        "Unable to parse repository URL for token injection"
                                    )
                        else:
                            logger.warning(
                                "Secret found but no recognized credential type (ssh-privatekey or token)"
                            )

                    except ApiException as e:
                        logger.error(
                            f"Failed to load git credentials from secret {secret_namespace}/{secret_name}: {e}"
                        )
                        raise

            # Clone repository with authentication
            try:
                if git_env:
                    # Use SSH authentication
                    repo = git.Repo.clone_from(
                        authenticated_url, temp_dir, branch=branch, env=git_env
                    )
                else:
                    # Use HTTPS (with or without token)
                    repo = git.Repo.clone_from(
                        authenticated_url, temp_dir, branch=branch
                    )
            finally:
                # Clean up SSH key file if it was created
                if ssh_key_file and os.path.exists(ssh_key_file.name):
                    os.unlink(ssh_key_file.name)

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
            # Create an empty file - it will be wrapped in a Modal app structure later
            dummy_app = os.path.join(temp_dir, "main.py")
            with open(dummy_app, "w") as f:
                f.write("# Placeholder for container-based app\n")

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
        """Build Modal application configuration

        Note: Compute, scaling, webhooks, and schedule should be defined
        in the user's Modal app file, not in the CRD spec.
        """
        config = {"app_name": spec["appName"], "environment": env_vars}

        return config

    async def _execute_modal_deploy(
        self, source_path: str, config: Dict[str, Any], name: str
    ) -> Dict[str, Any]:
        """Execute the actual Modal deployment

        Deploys the user's Modal app file directly without modification.
        """
        logger.info(f"Executing Modal deployment for {name}")
        logger.info(f"Deploying source file: {source_path}")

        try:
            # Set environment variables for Modal
            env = os.environ.copy()
            env.update(config.get("environment", {}))

            # Check if Modal CLI is available
            try:
                which_process = await asyncio.create_subprocess_exec(
                    "which",
                    "modal",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                which_stdout, _ = await which_process.communicate()

                if which_process.returncode != 0:
                    raise FileNotFoundError("Modal CLI not found")

                logger.info(f"Using Modal CLI at: {which_stdout.decode().strip()}")

            except (FileNotFoundError, OSError):
                logger.error(
                    "Modal CLI not found. Please install it with: pip install modal"
                )
                raise RuntimeError(
                    "Modal CLI not available. Install with: pip install modal"
                )

            # Run modal deploy command directly on the user's file
            cmd = ["modal", "deploy", source_path]
            logger.info(f"Running command: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=os.path.dirname(source_path),
            )

            stdout, stderr = await process.communicate()
            returncode = process.returncode

            if stdout:
                logger.info(f"Modal deploy stdout: {stdout.decode('utf-8')}")
            if stderr:
                logger.info(f"Modal deploy stderr: {stderr.decode('utf-8')}")

            if returncode != 0:
                error_msg = (
                    stderr.decode("utf-8") if stderr else "Unknown deployment error"
                )
                raise RuntimeError(f"Modal deployment failed: {error_msg}")

            # Parse deployment result from Modal CLI output
            output_text = stdout.decode("utf-8") if stdout else ""

            import re

            # Extract app name from the source file for reference
            actual_app_name = None
            try:
                actual_app_name = self._extract_app_name_from_source(source_path)
                if actual_app_name:
                    logger.info(
                        f"Extracted app name from source file: {actual_app_name}"
                    )
            except Exception as e:
                logger.debug(f"Could not extract app name from source: {e}")

            # If still no app name, use config as fallback
            if not actual_app_name:
                actual_app_name = config.get("app_name", name)

            # Query Modal to get the actual app ID for the deployed app
            logger.info(f"Querying Modal to get app ID for '{actual_app_name}'...")
            actual_app_id = await self._get_app_id_by_name(actual_app_name)

            if actual_app_id:
                logger.info(f"Successfully retrieved app ID: {actual_app_id}")
            else:
                logger.warning(
                    f"Could not retrieve app ID for '{actual_app_name}'. "
                    "Deletion will query Modal API to find the app."
                )

            result = {
                "app_id": actual_app_id,  # Real app ID from Modal
                "app_name": actual_app_name,  # For reference
                "url": None,
            }

            # Try to extract URL from Modal deploy output
            if output_text:
                url_pattern = r"https://[^\s]+\.modal\.run[^\s]*"
                urls = re.findall(url_pattern, output_text)
                if urls:
                    result["url"] = urls[0]

            logger.info(f"Modal deployment successful for {name}")
            logger.info(f"  App ID: {actual_app_id or 'not retrieved'}")
            logger.info(f"  App Name: {actual_app_name}")
            logger.info(f"  URL: {result.get('url') or 'none'}")

            return result

        except Exception as e:
            logger.error(f"Modal deployment failed for {name}: {e}")
            raise

    def _extract_app_name_from_source(self, source_path: str) -> Optional[str]:
        """Extract the actual app name from a Modal Python source file

        Looks for patterns like:
        - app = modal.App("app-name")
        - app = App("app-name")
        - modal.App("app-name")
        """
        try:
            with open(source_path, "r") as f:
                content = f.read()

            import re

            # Common patterns for Modal app definition
            patterns = [
                r'modal\.App\([\'"]([a-zA-Z0-9_-]+)[\'"]\)',  # modal.App("name")
                r'App\([\'"]([a-zA-Z0-9_-]+)[\'"]\)',  # App("name")
                r'=\s*modal\.App\([\'"]([a-zA-Z0-9_-]+)[\'"]\)',  # var = modal.App("name")
                r'=\s*App\([\'"]([a-zA-Z0-9_-]+)[\'"]\)',  # var = App("name")
            ]

            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    app_name = match.group(1)
                    logger.info(f"Extracted app name from source file: {app_name}")
                    return app_name

            logger.warning(f"Could not find app name pattern in {source_path}")
            return None

        except Exception as e:
            logger.error(f"Error reading source file {source_path}: {e}")
            return None

    async def _stop_modal_app(self, app_id: str):
        """Stop a Modal application using its app ID

        Args:
            app_id: Modal app ID (format: ap-xxxxx)
        """
        logger.info(f"Stopping Modal app with ID: {app_id}")

        try:
            # Check if Modal CLI is available
            try:
                which_process = await asyncio.create_subprocess_exec(
                    "which",
                    "modal",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                which_stdout, _ = await which_process.communicate()

                if which_process.returncode != 0:
                    logger.warning("Modal CLI not found, skipping app stop")
                    return
            except (FileNotFoundError, OSError):
                logger.warning("Modal CLI not available, skipping app stop")
                return

            # Use modal app stop command with the app ID
            cmd = ["modal", "app", "stop", app_id]
            logger.info(f"Running command: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()
            returncode = process.returncode

            if stdout:
                logger.info(f"Modal stop stdout: {stdout.decode('utf-8')}")

            stderr_text = stderr.decode("utf-8") if stderr else ""

            if returncode == 0:
                logger.info(f"Successfully stopped Modal app {app_id}")
                return

            # Check if app doesn't exist (already deleted)
            if (
                "not found" in stderr_text.lower()
                or "does not exist" in stderr_text.lower()
                or "could not find" in stderr_text.lower()
            ):
                logger.info(
                    f"Modal app '{app_id}' not found. "
                    "The app may have already been deleted or never deployed successfully."
                )
                return
            else:
                # Some other error occurred
                logger.warning(f"Modal stop stderr: {stderr_text}")
                logger.warning(
                    f"Modal app stop returned non-zero exit code {returncode}: {stderr_text}"
                )

        except Exception as e:
            # Log error but don't fail - app may already be deleted
            logger.warning(f"Error stopping Modal app {app_id}: {e}")
            logger.info("Continuing with deletion process")

    async def _get_app_id_by_name(self, app_name: str) -> Optional[str]:
        """Get the app ID for a deployed app by its name

        Args:
            app_name: The app name to search for

        Returns:
            The app ID (e.g., 'ap-xxxxx') if found, None otherwise
        """
        try:
            deployed_apps = await self._list_deployed_apps()

            # Try exact match first
            for app in deployed_apps:
                if app.get("name") == app_name:
                    return app.get("id")

            # Try case-insensitive match
            for app in deployed_apps:
                if app.get("name", "").lower() == app_name.lower():
                    return app.get("id")

            logger.warning(f"Could not find app ID for app name: {app_name}")
            return None

        except Exception as e:
            logger.error(f"Error getting app ID by name: {e}")
            return None

    async def _list_deployed_apps(self) -> List[Dict[str, str]]:
        """List all currently deployed Modal apps with their IDs using JSON output

        Returns a list of dicts with 'id' and 'name' keys.
        Example: [{'id': 'ap-xxxxx', 'name': 'my-app'}, ...]
        """
        try:
            cmd = ["modal", "app", "list", "--json"]
            logger.info(f"Running command: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                stderr_text = stderr.decode("utf-8") if stderr else "No error output"
                logger.warning(
                    f"Failed to list apps (exit code {process.returncode}): {stderr_text}"
                )
                return []

            # Parse JSON output
            import json

            output_text = stdout.decode("utf-8")
            logger.debug(f"Modal app list output: {output_text}")

            try:
                apps_data = json.loads(output_text)

                # Handle different possible JSON structures
                apps = []

                # If it's a list of app objects
                if isinstance(apps_data, list):
                    for app in apps_data:
                        if isinstance(app, dict):
                            # Try different possible field names for ID and name
                            # Modal uses "App ID" and "Description" with capitals and spaces
                            app_id = (
                                app.get("App ID")
                                or app.get("id")
                                or app.get("app_id")
                                or app.get("appId")
                            )
                            app_name = (
                                app.get("Description")
                                or app.get("description")
                                or app.get("name")
                                or app.get("app_name")
                                or app.get("appName")
                            )

                            # Filter by state - only include deployed apps
                            state = app.get("State", "").lower()

                            if app_id and state == "deployed":
                                apps.append({"id": app_id, "name": app_name or app_id})

                # If it's a dict with an 'apps' key
                elif isinstance(apps_data, dict) and "apps" in apps_data:
                    for app in apps_data["apps"]:
                        if isinstance(app, dict):
                            app_id = (
                                app.get("App ID")
                                or app.get("id")
                                or app.get("app_id")
                                or app.get("appId")
                            )
                            app_name = (
                                app.get("Description")
                                or app.get("description")
                                or app.get("name")
                                or app.get("app_name")
                                or app.get("appName")
                            )

                            # Filter by state - only include deployed apps
                            state = app.get("State", "").lower()

                            if app_id and state == "deployed":
                                apps.append({"id": app_id, "name": app_name or app_id})

                logger.info(f"Found {len(apps)} deployed apps via Modal API")

                return apps

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from modal app list: {e}")
                logger.debug(f"Raw output: {output_text}")

                # Fallback: try to parse as plain text (one app per line)
                logger.info("Attempting to parse output as plain text...")
                apps = []
                for line in output_text.split("\n"):
                    line = line.strip()
                    if (
                        line
                        and not line.startswith("#")
                        and "App" not in line
                        and "---" not in line
                    ):
                        parts = line.split()
                        if parts:
                            # Assume first column is app ID or name
                            apps.append(
                                {
                                    "id": parts[0],
                                    "name": parts[1] if len(parts) > 1 else parts[0],
                                }
                            )

                logger.info(f"Parsed {len(apps)} apps from plain text output")
                return apps

        except Exception as e:
            logger.warning(f"Error listing deployed apps: {e}")
            return []
