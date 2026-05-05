import json
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()

DATA_DIR = Path(__file__).parent.parent.parent / "data"

@router.get("/")
async def get_deployments():
    deployed_file = DATA_DIR / "deployed_models.json"
    if not deployed_file.exists():
        return []
    with open(deployed_file, "r") as f:
        return json.load(f)
