"""
api/deployment_manager.py
==========================
Manages vLLM model deployment lifecycle.

- Stores deployment state in SurrealDB (primary) + deployed_models.json (cache)
- Launches scripts/deploy_vllm.py as subprocess on deploy
- Health-checks running deployments
- Updates available_models.json when a model comes online
- Respects USE_GPU flag — refuses deployment when GPU is disabled
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

from api.llm_provider import is_gpu_enabled, get_available_models

DATA_DIR = Path(__file__).parent.parent / "data"
DEPLOYED_MODELS_FILE = DATA_DIR / "deployed_models.json"
AVAILABLE_MODELS_FILE = DATA_DIR / "available_models.json"
DEPLOY_SCRIPT = Path(__file__).parent.parent / "scripts" / "deploy_vllm.py"

# In-memory registry of active deployment processes
_active_processes: dict[str, subprocess.Popen] = {}


# ── SurrealDB Helpers ────────────────────────────────────────────────────────

async def _db_available() -> bool:
    """Check if SurrealDB repo_query is importable and working."""
    try:
        from open_notebook.database.repository import repo_query
        return True
    except Exception:
        return False


async def _ensure_deployment_table():
    """Create the vllm_deployment table if it doesn't exist."""
    try:
        from open_notebook.database.repository import repo_query
        await repo_query("""
            DEFINE TABLE IF NOT EXISTS vllm_deployment SCHEMAFULL;
            DEFINE FIELD deployment_id ON vllm_deployment TYPE string;
            DEFINE FIELD model_id      ON vllm_deployment TYPE string;
            DEFINE FIELD model_name    ON vllm_deployment TYPE string;
            DEFINE FIELD status        ON vllm_deployment TYPE string;
            DEFINE FIELD endpoint      ON vllm_deployment TYPE string;
            DEFINE FIELD port          ON vllm_deployment TYPE int;
            DEFINE FIELD pid           ON vllm_deployment TYPE option<int>;
            DEFINE FIELD api_key       ON vllm_deployment TYPE string;
            DEFINE FIELD config        ON vllm_deployment TYPE object;
            DEFINE FIELD log_file      ON vllm_deployment TYPE option<string>;
            DEFINE FIELD created_at    ON vllm_deployment TYPE datetime DEFAULT time::now();
            DEFINE FIELD updated_at    ON vllm_deployment TYPE datetime DEFAULT time::now();
            DEFINE INDEX deployment_id_idx ON vllm_deployment FIELDS deployment_id UNIQUE;
        """)
    except Exception as e:
        logger.warning(f"Could not ensure vllm_deployment table: {e}")


async def _save_deployment_to_db(deployment: dict):
    """Upsert a deployment record in SurrealDB."""
    try:
        from open_notebook.database.repository import repo_query
        await _ensure_deployment_table()

        dep_id = deployment["deployment_id"]
        # Try update first, then create
        existing = await repo_query(
            "SELECT * FROM vllm_deployment WHERE deployment_id = $dep_id",
            {"dep_id": dep_id}
        )

        if existing:
            await repo_query(
                """UPDATE vllm_deployment SET
                    status = $status,
                    endpoint = $endpoint,
                    pid = $pid,
                    log_file = $log_file,
                    updated_at = time::now()
                WHERE deployment_id = $dep_id""",
                {
                    "dep_id": dep_id,
                    "status": deployment.get("status", "Unknown"),
                    "endpoint": deployment.get("endpoint", "--"),
                    "pid": deployment.get("pid"),
                    "log_file": deployment.get("log_file"),
                }
            )
        else:
            await repo_query(
                """CREATE vllm_deployment CONTENT {
                    deployment_id: $dep_id,
                    model_id: $model_id,
                    model_name: $model_name,
                    status: $status,
                    endpoint: $endpoint,
                    port: $port,
                    pid: $pid,
                    api_key: $api_key,
                    config: $config,
                    log_file: $log_file
                }""",
                {
                    "dep_id": dep_id,
                    "model_id": deployment.get("model_id", ""),
                    "model_name": deployment.get("model_name", ""),
                    "status": deployment.get("status", "Starting"),
                    "endpoint": deployment.get("endpoint", "--"),
                    "port": deployment.get("port", 8001),
                    "pid": deployment.get("pid"),
                    "api_key": deployment.get("api_key", ""),
                    "config": deployment.get("config", {}),
                    "log_file": deployment.get("log_file"),
                }
            )
    except Exception as e:
        logger.error(f"Failed to save deployment to DB: {e}")


async def _delete_deployment_from_db(deployment_id: str):
    """Remove a deployment record from SurrealDB."""
    try:
        from open_notebook.database.repository import repo_query
        await repo_query(
            "DELETE FROM vllm_deployment WHERE deployment_id = $dep_id",
            {"dep_id": deployment_id}
        )
    except Exception as e:
        logger.error(f"Failed to delete deployment from DB: {e}")


async def _get_deployments_from_db() -> list[dict]:
    """Fetch all deployment records from SurrealDB."""
    try:
        from open_notebook.database.repository import repo_query
        await _ensure_deployment_table()
        result = await repo_query("SELECT * FROM vllm_deployment ORDER BY created_at DESC")
        if result and isinstance(result, list):
            return result
        return []
    except Exception as e:
        logger.warning(f"Could not read deployments from DB: {e}")
        return []


# ── JSON File Helpers (fallback/cache) ───────────────────────────────────────

def _read_deployed_json() -> list[dict]:
    """Read deployed_models.json as fallback."""
    if not DEPLOYED_MODELS_FILE.exists():
        return []
    try:
        with open(DEPLOYED_MODELS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _write_deployed_json(deployments: list[dict]):
    """Write deployment list to deployed_models.json as cache."""
    try:
        with open(DEPLOYED_MODELS_FILE, "w") as f:
            json.dump(deployments, f, indent=2, default=str)
    except IOError as e:
        logger.error(f"Failed to write deployed_models.json: {e}")


def _sync_json_cache(deployments: list[dict]):
    """Sync SurrealDB deployments to the JSON cache file."""
    simplified = []
    for d in deployments:
        simplified.append({
            "deployment_id": d.get("deployment_id", ""),
            "model_id": d.get("model_id", ""),
            "model_name": d.get("model_name", ""),
            "status": d.get("status", "Unknown"),
            "endpoint": d.get("endpoint", "--"),
            "port": d.get("port", 8001),
            "api_key": d.get("api_key", "--"),
            "config": d.get("config", {}),
        })
    _write_deployed_json(simplified)


# ── Health Check ─────────────────────────────────────────────────────────────

def _health_check_sync(endpoint: str, timeout: int = 3) -> bool:
    """Synchronous health check for a vLLM endpoint."""
    import urllib.request
    import urllib.error

    try:
        url = f"{endpoint}/models"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


async def health_check(endpoint: str) -> bool:
    """Async health check for a vLLM endpoint."""
    return await asyncio.to_thread(_health_check_sync, endpoint)


# ── Core Deployment Manager ─────────────────────────────────────────────────

class DeploymentManager:
    """Manages the lifecycle of vLLM model deployments."""

    async def deploy_model(
        self,
        model_id: str,
        model_name: str,
        quantization: str | None = None,
        target_gpu: str | None = None,
        port: int | None = None,
        gpu_memory_utilization: float = 0.9,
        tensor_parallel_size: int = 1,
        max_model_len: int | None = None,
    ) -> dict:
        """
        Deploy a model via vLLM.

        1. Checks USE_GPU flag — raises if false
        2. Launches scripts/deploy_vllm.py as background subprocess
        3. Creates deployment record in SurrealDB
        4. Syncs to deployed_models.json cache
        5. Returns deployment status dict
        """
        if not is_gpu_enabled():
            raise PermissionError(
                "GPU mode is disabled. Set USE_GPU=true in .env to enable model deployment."
            )

        deployment_id = f"dep-{uuid.uuid4().hex[:8]}"
        api_key = f"aria-{uuid.uuid4().hex}"
        resolved_port = port or int(os.getenv("VLLM_PORT", "8001"))

        # Map model_id from registry to HuggingFace model name
        hf_model = self._resolve_hf_model(model_id, model_name)

        deployment = {
            "deployment_id": deployment_id,
            "model_id": model_id,
            "model_name": model_name or hf_model,
            "status": "Starting",
            "endpoint": f"http://localhost:{resolved_port}/v1",
            "port": resolved_port,
            "pid": None,
            "api_key": api_key,
            "config": {
                "quantization": quantization,
                "target_gpu": target_gpu,
                "gpu_memory_utilization": gpu_memory_utilization,
                "tensor_parallel_size": tensor_parallel_size,
                "max_model_len": max_model_len,
                "hf_model": hf_model,
            },
            "log_file": None,
        }

        # Save to DB immediately with "Starting" status
        await _save_deployment_to_db(deployment)
        await self._sync_cache()

        # Launch the deploy script in background
        asyncio.create_task(
            self._run_deploy_subprocess(deployment, hf_model, resolved_port,
                                         quantization, gpu_memory_utilization,
                                         tensor_parallel_size, max_model_len)
        )

        logger.info(f"Deployment {deployment_id} initiated for {hf_model} on port {resolved_port}")
        return deployment

    async def _run_deploy_subprocess(
        self, deployment: dict, hf_model: str, port: int,
        quantization: str | None, gpu_mem: float, tp: int,
        max_model_len: int | None,
    ):
        """Run the deploy_vllm.py script and update status based on output."""
        dep_id = deployment["deployment_id"]

        cmd = [
            sys.executable, str(DEPLOY_SCRIPT),
            "--model", hf_model,
            "--port", str(port),
            "--gpu-memory-utilization", str(gpu_mem),
            "--tensor-parallel-size", str(tp),
        ]
        if quantization:
            cmd.extend(["--quantization", quantization])
        if max_model_len:
            cmd.extend(["--max-model-len", str(max_model_len)])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _active_processes[dep_id] = process

            # Read stdout lines for status updates
            async for line in process.stdout:
                line_str = line.decode().strip()
                if not line_str:
                    continue

                try:
                    status_msg = json.loads(line_str)
                    new_status = status_msg.get("status", "")

                    if new_status == "running":
                        deployment["status"] = "Running"
                        deployment["pid"] = status_msg.get("pid")
                        deployment["endpoint"] = status_msg.get("endpoint", deployment["endpoint"])
                        deployment["log_file"] = status_msg.get("log_file")
                        await _save_deployment_to_db(deployment)
                        await self._sync_cache()
                        logger.info(f"Deployment {dep_id} is now RUNNING on {deployment['endpoint']}")

                    elif new_status in ("failed", "timeout"):
                        deployment["status"] = "Failed"
                        deployment["log_file"] = status_msg.get("log_file")
                        await _save_deployment_to_db(deployment)
                        await self._sync_cache()
                        logger.error(f"Deployment {dep_id} FAILED: {status_msg.get('reason', 'unknown')}")

                    elif new_status == "launched":
                        deployment["pid"] = status_msg.get("pid")
                        deployment["log_file"] = status_msg.get("log_file")
                        await _save_deployment_to_db(deployment)

                except json.JSONDecodeError:
                    logger.debug(f"Non-JSON output from deploy script: {line_str}")

            await process.wait()

        except Exception as e:
            logger.error(f"Deploy subprocess error for {dep_id}: {e}")
            deployment["status"] = "Failed"
            await _save_deployment_to_db(deployment)
            await self._sync_cache()
        finally:
            _active_processes.pop(dep_id, None)

    async def undeploy_model(self, deployment_id: str) -> dict:
        """Stop a running deployment and clean up."""
        deployments = await self.get_deployments()
        deployment = next((d for d in deployments if d.get("deployment_id") == deployment_id), None)

        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")

        # Kill the vLLM process if we have its PID
        pid = deployment.get("pid")
        if pid:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                else:
                    os.kill(pid, signal.SIGTERM)
                logger.info(f"Sent SIGTERM to PID {pid} for deployment {deployment_id}")
            except (ProcessLookupError, PermissionError) as e:
                logger.warning(f"Could not kill PID {pid}: {e}")

        # Kill subprocess if tracked
        proc = _active_processes.pop(deployment_id, None)
        if proc and proc.returncode is None:
            try:
                proc.terminate()
            except Exception:
                pass

        # Remove from DB and cache
        await _delete_deployment_from_db(deployment_id)
        await self._sync_cache()

        return {"deployment_id": deployment_id, "status": "Stopped"}

    async def get_deployments(self) -> list[dict]:
        """Get all deployments. Tries SurrealDB first, falls back to JSON."""
        if await _db_available():
            db_deps = await _get_deployments_from_db()
            if db_deps:
                return db_deps

        return _read_deployed_json()

    async def get_deployment(self, deployment_id: str) -> dict | None:
        """Get a single deployment by ID."""
        deployments = await self.get_deployments()
        return next((d for d in deployments if d.get("deployment_id") == deployment_id), None)

    async def health_check_deployment(self, deployment_id: str) -> dict:
        """Health-check a specific deployment."""
        deployment = await self.get_deployment(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")

        endpoint = deployment.get("endpoint", "")
        is_healthy = await health_check(endpoint) if endpoint and endpoint != "--" else False

        # Update status if it changed
        current_status = deployment.get("status", "Unknown")
        if is_healthy and current_status != "Running":
            deployment["status"] = "Running"
            await _save_deployment_to_db(deployment)
            await self._sync_cache()
        elif not is_healthy and current_status == "Running":
            deployment["status"] = "Unhealthy"
            await _save_deployment_to_db(deployment)
            await self._sync_cache()

        return {
            "deployment_id": deployment_id,
            "healthy": is_healthy,
            "status": deployment.get("status", "Unknown"),
            "endpoint": endpoint,
        }

    async def _sync_cache(self):
        """Sync current DB state to deployed_models.json."""
        try:
            deployments = await self.get_deployments()
            _sync_json_cache(deployments)
        except Exception as e:
            logger.warning(f"Failed to sync deployment cache: {e}")

    def _resolve_hf_model(self, model_id: str, model_name: str) -> str:
        """Map a registry model_id to a HuggingFace model name."""
        # Common mappings from model_registry.json IDs to HF names
        hf_map = {
            "qwen-27b": "Qwen/Qwen2.5-27B-Instruct",
            "qwen-7b": "Qwen/Qwen2.5-7B-Instruct",
            "qwen-vl": "Qwen/Qwen2-VL-7B-Instruct",
            "bge-m3": "BAAI/bge-m3",
            "qwen3-tts": "Qwen/Qwen3-TTS-1.7B",
        }
        return hf_map.get(model_id, model_id)


# Global singleton
deployment_manager = DeploymentManager()
