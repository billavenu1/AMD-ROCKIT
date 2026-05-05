import json
import uuid
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

from api.llm_provider import get_available_models

router = APIRouter()

DATA_DIR = Path(__file__).parent.parent.parent / "data"

class DeployRequest(BaseModel):
    model_id: str
    quantization: str
    target_gpu: str

@router.get("/models")
async def get_models():
    models_file = DATA_DIR / "model_registry.json"
    if not models_file.exists():
        return []
    with open(models_file, "r") as f:
        return json.load(f)

@router.get("/available-models")
async def get_available_chat_models():
    """Return the list of available chat/LLM models from available_models.json."""
    return get_available_models()

@router.post("/deploy")
async def deploy_model(request: DeployRequest):
    deployment_id = f"dep-{uuid.uuid4().hex[:8]}"
    endpoint = f"/v1/chat/completions"
    api_key = f"aria-{uuid.uuid4().hex}"
    
    deployment_data = {
        "deployment_id": deployment_id,
        "model_id": request.model_id,
        "status": "Starting",
        "endpoint": endpoint,
        "api_key": api_key,
        "config": {
            "quantization": request.quantization,
            "target_gpu": request.target_gpu
        }
    }
    
    deployed_file = DATA_DIR / "deployed_models.json"
    deployments = []
    if deployed_file.exists():
        with open(deployed_file, "r") as f:
            try:
                deployments = json.load(f)
            except json.JSONDecodeError:
                deployments = []
    
    deployments.append(deployment_data)
    
    with open(deployed_file, "w") as f:
        json.dump(deployments, f, indent=2)
        
    return deployment_data
