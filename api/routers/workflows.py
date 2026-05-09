"""
api/routers/workflows.py
=========================
REST API for ARIA Agentic Workflows.

Endpoints:
  GET    /api/workflows              → List all workflows
  POST   /api/workflows              → Create a new workflow
  GET    /api/workflows/{id}         → Get workflow details
  PUT    /api/workflows/{id}         → Update workflow config
  POST   /api/workflows/{id}/publish → Build & activate the pipeline
  POST   /api/workflows/{id}/invoke  → Execute the pipeline
  DELETE /api/workflows/{id}         → Stop & remove
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from api.workflow_runtime import WorkflowConfig, WorkflowRuntime

router = APIRouter()

# ── Persistence ─────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent.parent / "data"
WORKFLOWS_FILE = DATA_DIR / "workflows.json"


def _load_workflows() -> List[dict]:
    """Load all workflow definitions from disk."""
    if not WORKFLOWS_FILE.exists():
        return []
    with open(WORKFLOWS_FILE, "r") as f:
        return json.load(f)


def _save_workflows(workflows: List[dict]) -> None:
    """Persist workflow definitions to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(WORKFLOWS_FILE, "w") as f:
        json.dump(workflows, f, indent=2, default=str)


def _find_workflow(workflow_id: str) -> tuple[List[dict], dict]:
    """Find a workflow by ID. Returns (all_workflows, matched_workflow)."""
    workflows = _load_workflows()
    for wf in workflows:
        if wf["workflow_id"] == workflow_id:
            return workflows, wf
    raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")


# ── In-memory runtime registry ──────────────────────────────────────────────

ACTIVE_RUNTIMES: Dict[str, WorkflowRuntime] = {}


def _boot_runtime(wf: dict) -> WorkflowRuntime:
    """Create a WorkflowRuntime from a persisted workflow definition."""
    cfg = wf.get("config", {})
    knowledge = cfg.get("knowledge", {})
    runtime = WorkflowRuntime(
        WorkflowConfig(
            model=cfg.get("model", "Qwen 7B Instruct"),
            instructions=cfg.get("instructions", ""),
            knowledge_type=knowledge.get("type", ""),
            knowledge_source=knowledge.get("source", ""),
            tools=cfg.get("tools", []),
        )
    )
    ACTIVE_RUNTIMES[wf["workflow_id"]] = runtime
    return runtime


def _restore_published_workflows() -> None:
    """On module load, restore runtimes for any previously-published workflows."""
    for wf in _load_workflows():
        if wf.get("status") == "running":
            try:
                _boot_runtime(wf)
                logger.info(f"Restored workflow runtime: {wf['workflow_id']} ({wf.get('name', '')})")
            except Exception as e:
                logger.warning(f"Failed to restore workflow {wf['workflow_id']}: {e}")


# Restore on import
_restore_published_workflows()


# ── Request / Response Models ────────────────────────────────────────────────

class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., description="Human-readable workflow name")
    model: str = Field("Qwen 7B Instruct", description="LLM model ID")
    instructions: str = Field("", description="System prompt / instructions")
    knowledge: Dict[str, str] = Field(
        default_factory=dict,
        description='Knowledge config, e.g. {"type": "Vision", "source": "Image"}',
    )
    tools: List[str] = Field(default_factory=list, description="Active tool names")


class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    instructions: Optional[str] = None
    knowledge: Optional[Dict[str, str]] = None
    tools: Optional[List[str]] = None


class WorkflowInvokeRequest(BaseModel):
    message: str = Field(..., description="User message to send to the workflow")


class WorkflowResponse(BaseModel):
    workflow_id: str
    name: str
    status: str
    endpoint: Optional[str] = None
    created_at: str
    published_at: Optional[str] = None
    config: Dict[str, Any]
    metrics: Optional[Dict[str, Any]] = None


class WorkflowInvokeResponse(BaseModel):
    workflow_id: str
    response: str
    latency_ms: float
    knowledge_context: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[WorkflowResponse])
async def list_workflows():
    """List all saved workflows (draft + running)."""
    workflows = _load_workflows()
    results = []
    for wf in workflows:
        # Attach live metrics if runtime exists
        metrics = None
        rt = ACTIVE_RUNTIMES.get(wf["workflow_id"])
        if rt:
            metrics = {
                "total_invocations": rt.metrics.total_invocations,
                "avg_latency_ms": round(rt.metrics.avg_latency_ms, 1),
            }
        results.append(WorkflowResponse(
            workflow_id=wf["workflow_id"],
            name=wf.get("name", "Untitled"),
            status=wf.get("status", "draft"),
            endpoint=wf.get("endpoint"),
            created_at=wf.get("created_at", ""),
            published_at=wf.get("published_at"),
            config=wf.get("config", {}),
            metrics=metrics,
        ))
    return results


@router.post("/", response_model=WorkflowResponse)
async def create_workflow(request: WorkflowCreateRequest):
    """Create (save) a new workflow definition."""
    workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    wf = {
        "workflow_id": workflow_id,
        "name": request.name,
        "status": "draft",
        "endpoint": None,
        "created_at": now,
        "published_at": None,
        "config": {
            "model": request.model,
            "instructions": request.instructions,
            "knowledge": request.knowledge,
            "tools": request.tools,
        },
    }

    workflows = _load_workflows()
    workflows.append(wf)
    _save_workflows(workflows)

    logger.info(f"Created workflow: {workflow_id} ({request.name})")
    return WorkflowResponse(
        workflow_id=workflow_id,
        name=request.name,
        status="draft",
        endpoint=None,
        created_at=now,
        published_at=None,
        config=wf["config"],
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str):
    """Get details of a single workflow."""
    _, wf = _find_workflow(workflow_id)
    metrics = None
    rt = ACTIVE_RUNTIMES.get(workflow_id)
    if rt:
        metrics = {
            "total_invocations": rt.metrics.total_invocations,
            "avg_latency_ms": round(rt.metrics.avg_latency_ms, 1),
        }
    return WorkflowResponse(
        workflow_id=wf["workflow_id"],
        name=wf.get("name", "Untitled"),
        status=wf.get("status", "draft"),
        endpoint=wf.get("endpoint"),
        created_at=wf.get("created_at", ""),
        published_at=wf.get("published_at"),
        config=wf.get("config", {}),
        metrics=metrics,
    )


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(workflow_id: str, request: WorkflowUpdateRequest):
    """Update a workflow's configuration."""
    workflows, wf = _find_workflow(workflow_id)

    if request.name is not None:
        wf["name"] = request.name
    if request.model is not None:
        wf["config"]["model"] = request.model
    if request.instructions is not None:
        wf["config"]["instructions"] = request.instructions
    if request.knowledge is not None:
        wf["config"]["knowledge"] = request.knowledge
    if request.tools is not None:
        wf["config"]["tools"] = request.tools

    _save_workflows(workflows)

    # If runtime is active, rebuild it with new config
    if workflow_id in ACTIVE_RUNTIMES:
        _boot_runtime(wf)
        logger.info(f"Hot-reloaded workflow runtime: {workflow_id}")

    return WorkflowResponse(
        workflow_id=wf["workflow_id"],
        name=wf.get("name", "Untitled"),
        status=wf.get("status", "draft"),
        endpoint=wf.get("endpoint"),
        created_at=wf.get("created_at", ""),
        published_at=wf.get("published_at"),
        config=wf.get("config", {}),
    )


@router.post("/{workflow_id}/publish", response_model=WorkflowResponse)
async def publish_workflow(workflow_id: str):
    """Build the pipeline and set the workflow to 'running'."""
    workflows, wf = _find_workflow(workflow_id)

    # Build runtime
    _boot_runtime(wf)

    # Update status
    now = datetime.now(timezone.utc).isoformat()
    wf["status"] = "running"
    wf["published_at"] = now
    wf["endpoint"] = f"/api/workflows/{workflow_id}/invoke"

    _save_workflows(workflows)
    logger.success(f"Published workflow: {workflow_id} ({wf.get('name', '')})")

    return WorkflowResponse(
        workflow_id=wf["workflow_id"],
        name=wf.get("name", "Untitled"),
        status="running",
        endpoint=wf["endpoint"],
        created_at=wf.get("created_at", ""),
        published_at=now,
        config=wf.get("config", {}),
        metrics={"total_invocations": 0, "avg_latency_ms": 0},
    )


@router.post("/{workflow_id}/invoke", response_model=WorkflowInvokeResponse)
async def invoke_workflow(workflow_id: str, request: WorkflowInvokeRequest):
    """Execute the workflow pipeline with a user message."""
    runtime = ACTIVE_RUNTIMES.get(workflow_id)
    if not runtime:
        # Try to find and boot it
        _, wf = _find_workflow(workflow_id)
        if wf.get("status") != "running":
            raise HTTPException(
                status_code=400,
                detail=f"Workflow '{workflow_id}' is not published. Publish it first.",
            )
        runtime = _boot_runtime(wf)

    result = await runtime.invoke(request.message)

    # Persist updated metrics
    workflows, wf = _find_workflow(workflow_id)
    wf["metrics"] = {
        "total_invocations": runtime.metrics.total_invocations,
        "avg_latency_ms": round(runtime.metrics.avg_latency_ms, 1),
    }
    _save_workflows(workflows)

    return WorkflowInvokeResponse(
        workflow_id=workflow_id,
        response=result["response"],
        latency_ms=result["latency_ms"],
        knowledge_context=result.get("knowledge_context"),
    )


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Stop and delete a workflow."""
    workflows, wf = _find_workflow(workflow_id)

    # Remove runtime if active
    if workflow_id in ACTIVE_RUNTIMES:
        del ACTIVE_RUNTIMES[workflow_id]

    workflows.remove(wf)
    _save_workflows(workflows)

    logger.info(f"Deleted workflow: {workflow_id}")
    return {"success": True, "message": f"Workflow '{workflow_id}' deleted"}
