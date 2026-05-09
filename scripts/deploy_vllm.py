"""
scripts/deploy_vllm.py
=======================
Standalone script to deploy a model via vLLM.
Called by the backend DeploymentManager when the "Deploy" button is clicked.

Usage:
    python scripts/deploy_vllm.py \\
        --model "Qwen/Qwen2.5-7B-Instruct" \\
        --port 8001 \\
        --quantization awq \\
        --gpu-memory-utilization 0.9

The script prints JSON status updates to stdout for the backend to capture.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time


def find_free_port(start: int = 8001, end: int = 8100) -> int:
    """Find a free TCP port in the given range."""
    import socket

    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}-{end}")


def health_check(base_url: str, timeout: int = 5) -> bool:
    """Check if the vLLM server is responding."""
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(f"{base_url}/models", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def emit(status: str, **kwargs):
    """Print a JSON status line for the backend to capture."""
    msg = {"status": status, **kwargs}
    print(json.dumps(msg), flush=True)


def deploy(
    model: str,
    port: int = 8001,
    host: str = "0.0.0.0",
    quantization: str | None = None,
    gpu_memory_utilization: float = 0.9,
    tensor_parallel_size: int = 1,
    max_model_len: int | None = None,
):
    """Launch vLLM serve as a subprocess and wait until it's healthy."""
    cmd = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", model,
        "--host", host,
        "--port", str(port),
        "--gpu-memory-utilization", str(gpu_memory_utilization),
        "--tensor-parallel-size", str(tensor_parallel_size),
    ]
    if quantization:
        cmd.extend(["--quantization", quantization])
    if max_model_len:
        cmd.extend(["--max-model-len", str(max_model_len)])

    emit("starting", model=model, port=port, cmd=" ".join(cmd))

    # Launch the process
    log_file = os.path.join(
        os.path.dirname(__file__), "..", "data",
        f"vllm_{model.replace('/', '_')}_{port}.log"
    )
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    with open(log_file, "w") as lf:
        process = subprocess.Popen(
            cmd,
            stdout=lf,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        )

    emit("launched", pid=process.pid, log_file=log_file)

    # Wait for health check (up to 5 minutes)
    base_url = f"http://localhost:{port}/v1"
    max_wait = 300  # 5 minutes
    start = time.time()
    healthy = False

    while time.time() - start < max_wait:
        # Check if process died
        if process.poll() is not None:
            emit("failed", pid=process.pid, reason="Process exited early",
                 returncode=process.returncode, log_file=log_file)
            sys.exit(1)

        if health_check(base_url):
            healthy = True
            break

        time.sleep(5)
        elapsed = int(time.time() - start)
        emit("waiting", pid=process.pid, elapsed_sec=elapsed)

    if healthy:
        emit(
            "running",
            pid=process.pid,
            endpoint=base_url,
            model=model,
            port=port,
            log_file=log_file,
        )
    else:
        # Timeout — kill the process
        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.terminate()
        except Exception:
            pass
        emit("timeout", pid=process.pid, reason=f"Health check failed after {max_wait}s")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Deploy a model via vLLM")
    parser.add_argument("--model", required=True, help="HuggingFace model name")
    parser.add_argument("--port", type=int, default=None, help="Port (auto-detect if not set)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--quantization", default=None, help="Quantization method (awq, gptq, etc.)")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.9)
    parser.add_argument("--tensor-parallel-size", type=int, default=1)
    parser.add_argument("--max-model-len", type=int, default=None)

    args = parser.parse_args()

    port = args.port or find_free_port()

    deploy(
        model=args.model,
        port=port,
        host=args.host,
        quantization=args.quantization,
        gpu_memory_utilization=args.gpu_memory_utilization,
        tensor_parallel_size=args.tensor_parallel_size,
        max_model_len=args.max_model_len,
    )


if __name__ == "__main__":
    main()
