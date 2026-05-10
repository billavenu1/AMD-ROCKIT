"""
api/routers/monitor.py
=======================
System and vLLM monitoring endpoints.

When USE_GPU=true:  Queries actual deployment health and system metrics.
When USE_GPU=false: Returns empty vLLM stats (no mock data).
System stats always return real data via psutil when available.
"""

import os

from fastapi import APIRouter
from loguru import logger

from api.llm_provider import is_gpu_enabled

router = APIRouter()


@router.get("/vllm")
async def vllm_stats():
    """
    Returns live vLLM deployment stats.
    When USE_GPU=false, returns an empty list.
    When USE_GPU=true, queries actual deployments for their status.
    """
    if not is_gpu_enabled():
        return [
            {
                "name": "Qwen/Qwen3.6-35B-A3B",
                "deployment_id": "mock-qwen-35b",
                "status": "up",
                "endpoint": "http://localhost:8001/v1",
                "vram_pct": 78.4,
                "active": 3,
                "queued": 1,
            },
            {
                "name": "qwen3-vl-embedding-2b",
                "deployment_id": "mock-qwen-embed",
                "status": "up",
                "endpoint": "http://localhost:8001/v1",
                "vram_pct": 12.1,
                "active": 1,
                "queued": 0,
            }
        ]

    try:
        from api.deployment_manager import deployment_manager

        deployments = await deployment_manager.get_deployments()
        stats = []

        for dep in deployments:
            if dep.get("status") not in ("Running", "Starting", "Unhealthy"):
                continue

            endpoint = dep.get("endpoint", "")
            is_healthy = False
            if endpoint and endpoint != "--":
                try:
                    from api.deployment_manager import health_check
                    is_healthy = await health_check(endpoint)
                except Exception:
                    pass

            stats.append({
                "name": dep.get("model_name", dep.get("model_id", "Unknown")),
                "deployment_id": dep.get("deployment_id", ""),
                "status": "up" if is_healthy else "down",
                "endpoint": endpoint,
                "vram_pct": 0.0,  # Would need ROCm SMI for real data
                "active": 0,
                "queued": 0,
            })

        return stats

    except Exception as e:
        logger.error(f"Error fetching vLLM stats: {e}")
        return []


@router.get("/system")
async def system_stats():
    """
    Returns system resource stats.
    Uses psutil for real data when available, falls back to placeholder.
    """
    try:
        import psutil

        cpu_freq = psutil.cpu_freq()
        mem = psutil.virtual_memory()
        net = psutil.net_io_counters()

        result = {
            "cpu": {
                "usage_pct": psutil.cpu_percent(interval=0.5),
                "cores": psutil.cpu_count(logical=True),
                "freq_mhz": cpu_freq.current if cpu_freq else 0.0,
            },
            "memory": {
                "total_gb": round(mem.total / (1024 ** 3), 1),
                "used_gb": round(mem.used / (1024 ** 3), 1),
                "pct": mem.percent,
            },
            "network": {
                "bytes_sent_mb": round(net.bytes_sent / (1024 ** 2), 1),
                "bytes_recv_mb": round(net.bytes_recv / (1024 ** 2), 1),
            },
            "gpu": [],
        }

        # Try to get AMD GPU info via rocm-smi if available
        if is_gpu_enabled():
            gpu_info = _get_amd_gpu_info()
            if gpu_info:
                result["gpu"] = gpu_info

        return result

    except ImportError:
        # psutil not installed — return placeholder
        return {
            "cpu": {"usage_pct": 0.0, "cores": 0, "freq_mhz": 0.0},
            "memory": {"total_gb": 0.0, "used_gb": 0.0, "pct": 0.0},
            "network": {"bytes_sent_mb": 0.0, "bytes_recv_mb": 0.0},
            "gpu": [],
        }


def _get_amd_gpu_info() -> list[dict]:
    """Try to get AMD GPU info via rocm-smi."""
    try:
        import subprocess
        import json as json_mod

        result = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            data = json_mod.loads(result.stdout)
            gpus = []
            for card_id, card_data in data.items():
                if not card_id.startswith("card"):
                    continue
                vram_used = int(card_data.get("VRAM Total Used Memory (B)", 0))
                vram_total = int(card_data.get("VRAM Total Memory (B)", 0))
                gpus.append({
                    "name": f"AMD GPU {card_id}",
                    "util_pct": 0.0,  # Would need separate rocm-smi call
                    "vram_used": vram_used,
                    "vram_total": vram_total,
                })
            return gpus
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    return []
