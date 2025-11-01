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

        # Try to get Modal app ID/name from multiple sources
        modal_app_id = None
        modal_app_name = spec.get("appName", name)
        source_path = None

        try:
            # First, try to get app ID from CRD status (persists across restarts)
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

            # Fall back to in-memory tracking if available
            if not modal_app_id:
                key = f"{namespace}/{name}"
                if key in self.deployed_apps:
                    app_info = self.deployed_apps[key]
                    modal_app_id = app_info.get("app_id")
                    source_path = app_info.get("source_path")
                    logger.info(
                        f"Found Modal app ID from in-memory tracking: {modal_app_id}"
                    )

            # Use app name as fallback identifier
            app_identifier = modal_app_id or modal_app_name
            logger.info(f"Deleting Modal app using identifier: {app_identifier}")

            # Stop/delete the Modal app
            await self._stop_modal_app(app_identifier)

            # Clean up local resources
            if source_path and os.path.exists(source_path):
                import shutil

                shutil.rmtree(source_path, ignore_errors=True)
                logger.info(f"Cleaned up local resources at {source_path}")

            # Remove from in-memory tracking if present
            key = f"{namespace}/{name}"
            if key in self.deployed_apps:
                del self.deployed_apps[key]

            logger.info(f"Successfully deleted {name} from Modal")

        except Exception as e:
            logger.error(f"Failed to delete {name}: {e}")
            # Don't raise - allow deletion to proceed even if Modal cleanup fails
            logger.warning(f"Continuing with deletion despite Modal cleanup error")

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
            deploy_script = self._create_deploy_script(source_path, config, name)

            # Deploy to Modal using the CLI
            logger.info(f"Deploying to Modal using script: {deploy_script}")

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

            # Run modal deploy command
            cmd = ["modal", "deploy", deploy_script]
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

            result = {
                "app_id": name,  # Modal app name
                "url": None,
            }

            # Try to extract URL from Modal deploy output
            if "webhooks" in config and output_text:
                # Look for URL patterns in Modal output
                import re

                url_pattern = r"https://[^\s]+\.modal\.run[^\s]*"
                urls = re.findall(url_pattern, output_text)
                if urls:
                    result["url"] = urls[0]
                else:
                    # Fallback URL construction
                    result["url"] = f"https://{name}--modal.run"

            logger.info(f"Modal deployment successful for {name}")
            return result

        except Exception as e:
            logger.error(f"Modal deployment failed for {name}: {e}")
            raise

    def _create_deploy_script(
        self, source_path: str, config: Dict[str, Any], name: str
    ) -> str:
        """Create a Python script to deploy to Modal using modern API"""
        script_dir = os.path.dirname(source_path)
        script_path = os.path.join(script_dir, "modal_app.py")

        app_name = config.get("app_name", name)
        compute_config = config.get("compute", {})
        webhook_config = config.get("webhooks", {})

        # Build compute configuration for Modal
        gpu_config = None
        if compute_config.get("gpu"):
            gpu_type = compute_config["gpu"]
            gpu_count = compute_config.get("gpu_count", 1)

            # Map GPU types from CRD to Modal's expected format
            # CRD accepts: T4, L4, A10, A100, A100-40GB, A100-80GB, L40S, H100/H100!, H200, B200
            # Handle GPU types that can be used directly as Python identifiers
            simple_gpu_types = {
                "T4": "T4",
                "L4": "L4",
                "A10": "A10",  # CRD uses A10, not A10G
                "A100": "A100",
                "L40S": "L40S",
                "H200": "H200",
                "B200": "B200",
                # Legacy support for types not in CRD but might be in use
                "A10G": "A10G",
                "V100": "V100",
                "K80": "K80",
                "A6000": "A6000",
            }

            gpu_type_upper = gpu_type.upper()

            # Handle special GPU types that need string format due to special characters
            if gpu_type_upper in ("A100-40GB", "A100-80GB"):
                # Modal supports A100-40GB and A100-80GB as string format or via constants
                # Use string format: gpu="A100-80GB:4" or modal.gpu.A100_80GB(count=4)
                # Try using underscore format for Python identifiers
                gpu_type_normalized = gpu_type_upper.replace("-", "_")
                gpu_config = f"modal.gpu.{gpu_type_normalized}(count={gpu_count})"
            elif gpu_type_upper in ("H100/H100!", "H100"):
                # Handle H100/H100! - Modal likely supports this as H100
                # Use H100 as the base type
                gpu_config = f"modal.gpu.H100(count={gpu_count})"
            elif gpu_type_upper in simple_gpu_types:
                # Standard GPU types that map directly
                mapped_gpu = simple_gpu_types[gpu_type_upper]
                gpu_config = f"modal.gpu.{mapped_gpu}(count={gpu_count})"
            else:
                # Fallback: use the GPU type as-is (for forward compatibility)
                # Try to create a valid Python identifier
                gpu_type_safe = (
                    gpu_type_upper.replace("-", "_").replace("/", "_").replace("!", "")
                )
                gpu_config = f"modal.gpu.{gpu_type_safe}(count={gpu_count})"
                logger.warning(
                    f"Unknown GPU type '{gpu_type}', using as-is: {gpu_type_safe}"
                )

        cpu_config = compute_config.get("cpu", "0.25")
        memory_mb = 512  # Default
        if compute_config.get("memory"):
            # Convert memory from string like "512Mi" to MB integer
            memory_str = compute_config["memory"]
            if memory_str.endswith("Mi"):
                memory_mb = int(memory_str[:-2])
            elif memory_str.endswith("Gi"):
                memory_mb = int(memory_str[:-2]) * 1024
            else:
                memory_mb = int(memory_str)

        timeout = compute_config.get("timeout", 300)

        # Build function decorator with compute resources
        function_decorator_args = ["image=image"]
        if gpu_config:
            function_decorator_args.append(f"gpu={gpu_config}")
        if cpu_config and cpu_config != "0.25":
            function_decorator_args.append(f"cpu={cpu_config}")
        if memory_mb != 512:  # Only add if different from default
            function_decorator_args.append(f"memory={memory_mb}")
        if timeout != 300:  # Only add if different from default
            function_decorator_args.append(f"timeout={timeout}")

        decorator_args_str = ", ".join(function_decorator_args)

        # Check if source_path contains actual Modal code
        if os.path.exists(source_path) and os.path.getsize(source_path) > 0:
            logger.info(f"Using existing Modal app from {source_path}")

            # Read the original source file
            with open(source_path, "r") as f:
                original_content = f.read()

            # Check if it's already a Modal app
            if "modal.App(" in original_content or (
                "import modal" in original_content
                and "app = modal.App" in original_content
            ):
                # It's already a Modal app - use it directly but update app name and decorators
                updated_content = self._update_modal_app_config(
                    original_content, app_name, decorator_args_str
                )
                script_content = updated_content
            else:
                # It's a regular Python file - wrap it in Modal app structure
                script_content = self._wrap_in_modal_app(
                    original_content,
                    app_name,
                    decorator_args_str,
                    cpu_config,
                    memory_mb,
                    compute_config,
                    timeout,
                )
        else:
            # No source file or empty - create a basic Modal app
            logger.warning(
                f"No source file found at {source_path}, creating basic Modal app"
            )
            script_content = self._create_basic_modal_app(
                app_name,
                decorator_args_str,
                webhook_config,
                cpu_config,
                memory_mb,
                compute_config,
                timeout,
            )

        with open(script_path, "w") as f:
            f.write(script_content)

        # Make script executable
        os.chmod(script_path, 0o755)

        return script_path

    async def _stop_modal_app(self, app_identifier: str):
        """Stop a Modal application using Modal CLI"""
        logger.info(f"Stopping Modal app {app_identifier}")

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

            # Use modal app stop command to stop/deactivate the app
            # Modal apps can be stopped which effectively deactivates them
            cmd = ["modal", "app", "stop", app_identifier]
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
            if stderr:
                stderr_text = stderr.decode("utf-8")
                # Check if app doesn't exist (expected case)
                if (
                    "not found" in stderr_text.lower()
                    or "does not exist" in stderr_text.lower()
                ):
                    logger.info(
                        f"Modal app {app_identifier} not found, may already be deleted"
                    )
                    return
                else:
                    logger.warning(f"Modal stop stderr: {stderr_text}")

            if returncode == 0:
                logger.info(f"Successfully stopped Modal app {app_identifier}")
            else:
                # Non-zero return code - check if it's because app doesn't exist
                error_msg = stderr.decode("utf-8") if stderr else "Unknown error"
                if (
                    "not found" in error_msg.lower()
                    or "does not exist" in error_msg.lower()
                ):
                    logger.info(
                        f"Modal app {app_identifier} not found, may already be deleted"
                    )
                else:
                    logger.warning(
                        f"Modal app stop returned non-zero exit code {returncode}: {error_msg}"
                    )

        except Exception as e:
            # Log error but don't fail - app may already be deleted
            logger.warning(f"Error stopping Modal app {app_identifier}: {e}")
            logger.info("Continuing with deletion process")

    def _update_modal_app_config(
        self, original_content: str, app_name: str, decorator_args_str: str
    ) -> str:
        """Update existing Modal app with new configuration"""
        import re

        # Ensure app variable is defined - Modal requires it at module level
        has_app_definition = "app = modal.App" in original_content or re.search(
            r"app\s*=\s*modal\.App", original_content
        )

        if not has_app_definition:
            # Add app definition if missing (this handles cases where import modal exists but app isn't defined)
            if "import modal" in original_content:
                # Find the import statement and add app after it
                import_pattern = r"(import modal[^\n]*)"
                replacement = (
                    rf"\1\n\n# Create the Modal app\napp = modal.App(\"{app_name}\")"
                )
                content = re.sub(import_pattern, replacement, original_content, count=1)
            else:
                # No import modal - add both
                content = f'import modal\n\n# Create the Modal app\napp = modal.App("{app_name}")\n\n{original_content}'
        else:
            # Update app name if it exists - only match app = modal.App(...) assignments
            content = re.sub(
                r'(app\s*=\s*)modal\.App\(["\'][^"\']*["\']\)',
                rf'\1modal.App("{app_name}")',
                original_content,
            )

        # Ensure image variable is defined - required for function decorators
        has_image_definition = re.search(r"image\s*=\s*modal\.Image", content)

        if not has_image_definition:
            # Add image definition after app definition
            # Find where app is defined and add image after it
            app_pattern = r"(app\s*=\s*modal\.App\([^\)]*\))"
            if re.search(app_pattern, content):
                # Insert image definition after app definition
                content = re.sub(
                    app_pattern,
                    r'\1\n\n# Configure compute resources\nimage = modal.Image.debian_slim().pip_install("fastapi", "uvicorn")',
                    content,
                    count=1,
                )
            else:
                # Fallback: add before first @app.function decorator
                content = re.sub(
                    r"(@app\.function)",
                    '# Configure compute resources\nimage = modal.Image.debian_slim().pip_install("fastapi", "uvicorn")\n\n\\1',
                    content,
                    count=1,
                )

        # Update @app.function decorators to include compute config
        # This is a simple approach - in production you'd want more sophisticated parsing
        content = re.sub(
            r"@app\.function\([^)]*\)", f"@app.function({decorator_args_str})", content
        )

        return content

    def _wrap_in_modal_app(
        self,
        original_content: str,
        app_name: str,
        decorator_args_str: str,
        cpu_config: str,
        memory_mb: int,
        compute_config: dict,
        timeout: int,
    ) -> str:
        """Wrap regular Python code in Modal app structure"""

        wrapped_content = f'''#!/usr/bin/env python3
"""
GitOps Modal app from source: {app_name}
Compute: CPU={cpu_config}, Memory={memory_mb}MB, GPU={compute_config.get('gpu', 'None')}, Timeout={timeout}s
"""
import modal

# Create the Modal app
app = modal.App("{app_name}")

# Configure compute resources
image = modal.Image.debian_slim().pip_install("fastapi", "uvicorn")

# Original source code wrapped in Modal function
@app.function({decorator_args_str})
def main():
    """Main function containing the original source code"""
{self._indent_code(original_content, 4)}

# Entry point for modal deploy
if __name__ == "__main__":
    print("Modal app '{app_name}' is ready for deployment")
'''
        return wrapped_content

    def _create_basic_modal_app(
        self,
        app_name: str,
        decorator_args_str: str,
        webhook_config: dict,
        cpu_config: str,
        memory_mb: int,
        compute_config: dict,
        timeout: int,
    ) -> str:
        """Create a basic Modal app when no source is available"""

        script_content = f'''#!/usr/bin/env python3
"""
Basic GitOps Modal app: {app_name}
Compute: CPU={cpu_config}, Memory={memory_mb}MB, GPU={compute_config.get('gpu', 'None')}, Timeout={timeout}s
"""
import modal

# Create the Modal app
app = modal.App("{app_name}")

# Configure compute resources
image = modal.Image.debian_slim().pip_install("fastapi", "uvicorn")

'''

        # Add function based on whether it's a webhook or regular function
        if webhook_config.get("enabled", False):
            # Create a web endpoint
            script_content += f'''
@app.function({decorator_args_str})
@modal.web_endpoint(method="GET")
def hello():
    """Simple web endpoint"""
    return {{"message": "Hello from Modal GitOps!", "app": "{app_name}"}}

@app.function({decorator_args_str})
@modal.web_endpoint(method="POST")  
def echo(request_data: dict):
    """Echo endpoint for POST requests"""
    return {{"echo": request_data, "app": "{app_name}"}}
'''
        else:
            # Create a regular function
            script_content += f'''
@app.function({decorator_args_str})
def hello_world():
    """Simple hello world function"""
    print("Hello from Modal GitOps!")
    return "Hello from {app_name}"

@app.function({decorator_args_str})
def process_data(data: str = "test"):
    """Example data processing function"""
    result = f"Processed: {{data}} in {app_name}"
    print(result)
    return result
'''

        script_content += f"""
# This allows the app to be deployed with 'modal deploy'
if __name__ == "__main__":
    print("Modal app '{app_name}' is ready for deployment")
"""

        return script_content

    def _indent_code(self, code: str, spaces: int) -> str:
        """Indent code by the specified number of spaces"""
        indent = " " * spaces
        lines = code.split("\n")
        indented_lines = [indent + line if line.strip() else line for line in lines]
        return "\n".join(indented_lines)
