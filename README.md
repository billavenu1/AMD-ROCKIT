# ROCKIT

**ROCKIT** is a robust multi-modal search, ingestion, and agentic intelligence application built around an advanced Next.js frontend, a FastAPI orchestration layer, and a SurrealDB graph engine, paired with isolated Vision Intelligence utilizing the Hugging Face `hipVS` ecosystem.

---

## 🚀 Quick Start (Starting the Application)

The application has been fully containerized and can be launched with single commands, depending on your OS and hardware. These commands start the full stack: Next.js Frontend, FastAPI Backend, SurrealDB, and Elyra (Jupyter Lab).

### Windows

**Dependencies:** Docker Desktop, PowerShell.

1.  **Standard Setup (CPU/General):**
    ```powershell
    .\setup.ps1
    .\dev.ps1
    ```
2.  **Access:**
    *   **Frontend:** [http://localhost:3000](http://localhost:3000)
    *   **API/Backend:** [http://localhost:5055](http://localhost:5055)
    *   **Elyra:** [http://localhost:8888/elyra/lab](http://localhost:8888/elyra/lab)

### Linux (Docker Containerized)

**Dependencies:** Docker Compose, Bash.

First, copy `.env.example` to `.env` if you haven't already:
```bash
cp .env.example .env
```

**1. CPU Mode (No AMD GPU):**
Use this to run the entire application on the CPU.
```bash
./start-linux-cpu.sh
```

**2. GPU Mode (AMD ROCm / GPU Passthrough):**
Use this if your system has an AMD GPU and ROCm installed. This will activate vLLM and HIPVS acceleration.
```bash
./start-linux-gpu.sh
```

**Access (Linux Standalone Container):**
*   **Frontend:** [http://localhost:8502](http://localhost:8502)
*   **API/Backend:** [http://localhost:5055](http://localhost:5055)
*   **Elyra:** [http://localhost:8888/elyra/lab](http://localhost:8888/elyra/lab)

---

## 🏗️ Architecture & Sections

The application is composed of several independent sections, all managed through Docker Compose or standalone scripts:

1.  **Frontend (`aria-frontend/`)**: Next.js 16 (React 19) client. Manages UI state, workflows, deployments, and chat interfaces.
2.  **API Backend (`api/` & `open_notebook/`)**: Python FastAPI server. Handles database connections, routes requests to LLMs via LangGraph, and orchestrates workflows.
3.  **SurrealDB**: The core database holding semantic embeddings, nodes, and relationships.
4.  **Elyra/Jupyter Workspace (`elyra_work/`)**: Data science workspace directly integrated with the SurrealDB endpoint.
5.  **Vision Intelligence (`HF_Space_hipVS/`)**: An isolated engine for multi-modal embedding, optimized heavily for AMD ROCm via `hipVS`. (See detailed breakdown below).

---

## 👁️ Vision Intelligence (HF Space + hipVS)

<div align="center">

### GPU-Accelerated Multimodal Search Engine

*Build isolated projects, ingest images and videos, search with natural language — all powered by AMD hipVS CAGRA graph indexes with NVMe-backed hot-swap memory management.*

</div>

### What Is This?

ROCKIT Vision Intelligence is an **open-source, self-hosted multimodal search engine** that lets you create isolated projects, ingest visual media (images, videos), and query them with natural language. It is designed to showcase GPU-accelerated approximate nearest-neighbor (ANN) search using the **hipVS CAGRA** graph index on AMD ROCm hardware.

The core idea is simple:
> **Upload media → Embed everything into a shared vector space → Build a CAGRA graph on the GPU → Search in microseconds → Let an LLM interpret the results.**

There is no database. There are no external API dependencies. Every embedding, every index, and every LLM inference can run **entirely on local hardware**.

### Key Features

#### 1. Multi-Project Isolation
Create **multiple projects**, each with its own sources, indexes, and configuration. Projects are fully isolated — ingesting media into one never affects another.

#### 2. Native Multimodal Embedding (No Captioning)
Unlike caption-then-embed pipelines, ROCKIT uses **true vision-language embedding models** that encode images, video frames, and text queries into the **same vector space** directly. No intermediate captioning step — no information loss.

| Tier | Model | Dim | Use Case |
|------|-------|-----|----------|
| GPU (large) | `Qwen/Qwen3-VL-Embedding-8B` | 4096 | Highest quality, production |
| GPU (small) | `Qwen/Qwen3-VL-Embedding-2B` | 2048 | Balanced speed / quality |
| CPU fallback | `openai/clip-vit-large-patch14` | 768 | Free-tier HF Spaces, dev |

#### 3. CAGRA Graph Index (hipVS)
The CAGRA graph index is the fastest known ANN algorithm for GPU-resident data. ROCKIT rebuilds the CAGRA graph on every insert because this project is **optimized for inference and query speed**, not ingestion throughput.

#### 4. NVMe → VRAM Async Hot-Swap
Indexes live in three tiers of memory. When a project is queried, its index is **asynchronously copied from NVMe into VRAM** via pinned-memory DMA, without blocking other projects. When VRAM fills up, least-recently-used indexes are evicted back to NVMe — not deleted.

#### 5. LLM-Interpreted Results
Raw vector search returns `(id, score)` tuples. Before showing results to the user, ROCKIT passes them through an LLM that interprets the matches, merges adjacent video timestamps into time ranges, and generates a human-readable summary.

| Tier | Model | Notes |
|------|-------|-------|
| Primary | `Qwen/Qwen3-35B-A3B` | MoE: 35B total, 3B active — fast + smart |
| Fallback | `Qwen/Qwen3-1.7B` | Tiny, runs on anything |
| API | HF Inference API | Zero local compute, free tier |

### GPU Compute Tiers

ROCKIT Vision automatically detects available hardware and selects the best backend:

| Tier | Backend | Search Latency (100K vectors) | When Used |
|------|---------|-------------------------------|-----------|
| 1 | CAGRA graph (hipVS / cuVS) | ~50 μs | AMD ROCm GPU + `hipvs` installed |
| 2 | Flat tensor (hipBLAS matmul) | ~2 ms | Any CUDA/ROCm GPU |
| 3 | NumPy cosine similarity | ~15 ms | CPU-only / free HF Space |

### Setup (Standalone Vision Interface)

If you only want to run the Hugging Face Gradio app independently:

```bash
cd HF_Space_hipVS
cp .env.example .env         # edit with your settings
pip install -r requirements.txt
python app.py                # starts on http://localhost:7860
```

For CAGRA acceleration on AMD:
```bash
pip install hipvs cupy-rocm   # enables Tier 1
export USE_GPU=true
python app.py
```
