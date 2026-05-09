"""
api/routers/deployments.py
===========================
Full CRUD router for vLLM model deployments.

Endpoints:
  GET    /                     — List all deployments
  POST   /                     — Deploy a new model (requires USE_GPU=true)
  DELETE /{deployment_id}      — Stop and remove a deployment
  GET    /{deployment_id}/health — Health check a deployment
  GET    /gpu-enabled          — Check if GPU mode is enabled
  GET    /registry             — List deployable models from model_registry.json
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from api.deployment_manager import deployment_manager
from api.llm_provider import is_gpu_enabled

router = APIRouter()

DATA_DIR = Path(__file__).parent.parent.parent / "data"


# ── Request/Response Models ──────────────────────────────────────────────────

class DeployRequest(BaseModel):
    model_id: str = Field(..., description="Model ID from model_registry.json (e.g. 'qwen-7b')")
    model_name: str = Field("", description="Human-readable model name")
    quantization: Optional[str] = Field(None, description="Quantization method (4-bit, 8-bit, awq, etc.)")
    target_gpu: Optional[str] = Field(None, description="Target GPU type (MI300X, MI250, etc.)")
    port: Optional[int] = Field(None, description="Port to deploy on (auto-detect if not set)")
    gpu_memory_utilization: float = Field(0.9, description="GPU memory utilization (0.0-1.0)")
    tensor_parallel_size: int = Field(1, description="Tensor parallel size")
    max_model_len: Optional[int] = Field(None, description="Maximum model context length")


class DeploymentResponse(BaseModel):
    deployment_id: str
    model_id: str
    model_name: str
    status: str
    endpoint: str
    port: int
    api_key: str
    config: dict


class HealthResponse(BaseModel):
    deployment_id: str
    healthy: bool
    status: str
    endpoint: str


class GPUStatusResponse(BaseModel):
    gpu_enabled: bool
    vllm_base_url: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/gpu-enabled", response_model=GPUStatusResponse)
async def gpu_enabled():
    """Check if GPU/vLLM mode is enabled."""
    import os
    return GPUStatusResponse(
        gpu_enabled=is_gpu_enabled(),
        vllm_base_url=os.getenv("VLLM_BASE_URL", "http://localhost:8001/v1"),
    )


@router.get("/registry")
async def get_model_registry():
    """Return the list of models available for deployment from model_registry.json."""
    registry_file = DATA_DIR / "model_registry.json"
    if not registry_file.exists():
        return []
    with open(registry_file, "r") as f:
        return json.load(f)


@router.get("/")
async def get_deployments():
    """List all deployments (from SurrealDB, fallback to JSON)."""
    try:
        deployments = await deployment_manager.get_deployments()
        return deployments
    except Exception as e:
        logger.error(f"Error fetching deployments: {e}")
        # Fallback to static JSON
        deployed_file = DATA_DIR / "deployed_models.json"
        if deployed_file.exists():
            with open(deployed_file, "r") as f:
                return json.load(f)
        return []


@router.post("/", response_model=DeploymentResponse)
async def deploy_model(request: DeployRequest):
    """
    Deploy a model via vLLM.
    Returns 403 if USE_GPU=false.
    """
    if not is_gpu_enabled():
        raise HTTPException(
            status_code=403,
            detail="GPU mode is disabled. Set USE_GPU=true in .env to enable model deployment."
        )

    try:
        deployment = await deployment_manager.deploy_model(
            model_id=request.model_id,
            model_name=request.model_name,
            quantization=request.quantization,
            target_gpu=request.target_gpu,
            port=request.port,
            gpu_memory_utilization=request.gpu_memory_utilization,
            tensor_parallel_size=request.tensor_parallel_size,
            max_model_len=request.max_model_len,
        )
        return DeploymentResponse(
            deployment_id=deployment["deployment_id"],
            model_id=deployment["model_id"],
            model_name=deployment.get("model_name", ""),
            status=deployment["status"],
            endpoint=deployment.get("endpoint", "--"),
            port=deployment.get("port", 8001),
            api_key=deployment.get("api_key", ""),
            config=deployment.get("config", {}),
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error deploying model: {e}")
        raise HTTPException(status_code=500, detail=f"Deployment failed: {str(e)}")


@router.delete("/{deployment_id}")
async def undeploy_model(deployment_id: str):
    """Stop and remove a deployment."""
    try:
        result = await deployment_manager.undeploy_model(deployment_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error undeploying model: {e}")
        raise HTTPException(status_code=500, detail=f"Undeploy failed: {str(e)}")


@router.get("/{deployment_id}/health", response_model=HealthResponse)
async def check_health(deployment_id: str):
    """Health check a specific deployment."""
    try:
        result = await deployment_manager.health_check_deployment(deployment_id)
        return HealthResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error checking deployment health: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")
