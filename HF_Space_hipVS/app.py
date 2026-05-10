#!/usr/bin/env python3
"""
HF_Space_hipVS/app.py
=====================
ARIA Vision Intelligence — Hugging Face Space

Multi-project multimodal search engine.
  - Embedding: Qwen3-VL-Embedding (GPU) / CLIP (CPU) — direct, no captioning
  - LLM:       Qwen3-35B-A3B -> Qwen3-1.7B -> HF Inference API
  - Storage:   .npz + .cagra on NVMe, optional HF Dataset backup
  - GPU:       CAGRA (hipVS) -> PyTorch hipBLAS -> NumPy CPU
"""

import logging
import sys
from pathlib import Path

import gradio as gr

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("aria-vision")

from config import (
    USE_GPU, EMBED_MODEL, EMBED_DIM, LLM_MODEL, LLM_FALLBACK,
    FRAME_EVERY_SEC, HF_TOKEN, HF_DATASET_REPO, AUTO_SEED,
    DEFAULT_PROJECT,
)
from vector_store import get_store, list_projects
from ingest import (
    ingest_images, ingest_videos,
    ingest_single_image, ingest_single_video,
    HAS_FFMPEG,
)
from search import search_images, search_videos
import seed_data


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_system_info(project: str = DEFAULT_PROJECT) -> str:
    img_store = get_store(project, "image_index")
    vid_store = get_store(project, "video_index")
    return "\n".join([
        f"## System Status (project: `{project}`)\n",
        "| Setting | Value |",
        "|---------|-------|",
        f"| GPU Mode | {'Enabled' if USE_GPU else 'Disabled (CPU)'} |",
        f"| Search Backend | {img_store.mode} |",
        f"| Embed Model | `{EMBED_MODEL}` ({EMBED_DIM}d) |",
        f"| LLM | `{LLM_MODEL}` / `{LLM_FALLBACK}` |",
        f"| ffmpeg | {'Yes' if HAS_FFMPEG else 'No'} |",
        f"| Image Index | {img_store.count} vectors ({('VRAM' if img_store.in_vram else 'NVMe')}) |",
        f"| Video Index | {vid_store.count} vectors ({('VRAM' if vid_store.in_vram else 'NVMe')}) |",
        f"| Projects | {', '.join(list_projects()) or 'none'} |",
    ])


def get_projects_list() -> list[str]:
    projects = list_projects()
    if DEFAULT_PROJECT not in projects:
        projects.insert(0, DEFAULT_PROJECT)
    return projects


# ── Callbacks ────────────────────────────────────────────────────────────────

def handle_image_upload(files, project, progress=gr.Progress()):
    if not files:
        return "No files uploaded.", get_system_info(project)
    results = []
    for i, f in enumerate(files):
        progress((i + 1) / len(files), desc=f"Embedding {Path(f).name}...")
        ok, msg = ingest_single_image(f, project=project)
        results.append(msg)
    return "\n".join(results), get_system_info(project)


def handle_video_upload(files, project, progress=gr.Progress()):
    if not files:
        return "No files uploaded.", get_system_info(project)
    results = []
    for f in files:
        count, msg = ingest_single_video(f, project=project, progress_callback=progress)
        results.append(msg)
    return "\n".join(results), get_system_info(project)


def handle_batch_ingest(project, progress=gr.Progress()):
    img_count, img_log = ingest_images(project=project, progress_callback=progress)
    vid_count, vid_log = ingest_videos(project=project, progress_callback=progress)
    log = (
        f"=== Batch Ingest [{project}] ===\n\n"
        f"-- Images --\n{img_log}\n\n"
        f"-- Videos --\n{vid_log}\n\n"
        f"Total: {img_count} images + {vid_count} video frames"
    )
    return log, get_system_info(project)


def handle_seed(project, progress=gr.Progress()):
    count, log = seed_data.run(project=project, progress_callback=progress)
    return log, get_system_info(project)


def handle_clear(project):
    get_store(project, "image_index").clear()
    get_store(project, "video_index").clear()
    return f"All indexes cleared for project '{project}'.", get_system_info(project)


def handle_search(query, mode, top_k, project):
    if not query.strip():
        return "Please enter a search query.", ""

    if mode == "Image Search":
        result = search_images(query, project=project, top_k=int(top_k))
        summary = result["llm_summary"]
        rows = []
        for r in result["results"]:
            rows.append(f"| {r.get('file_name', '?')} | {r.get('resolution', '-')} | {r.get('score', 0):.4f} |")
        detail = ""
        if rows:
            detail = (
                "\n\n---\n\n### Raw Results\n\n"
                "| File | Resolution | Score |\n"
                "|------|-----------|-------|\n" + "\n".join(rows)
            )
        return summary + detail, result["store_info"]

    else:
        result = search_videos(query, project=project, top_k=int(top_k))
        summary = result["llm_summary"]
        rows = []
        for m in result["matches"]:
            rows.append(f"| {m['video_name']} | {m['start']} - {m['end']} | {m['score']:.4f} | {m['frames']} |")
        detail = ""
        if rows:
            detail = (
                "\n\n---\n\n### Raw Matches\n\n"
                "| Video | Time Range | Score | Frames |\n"
                "|-------|-----------|-------|--------|\n" + "\n".join(rows)
            )
        return summary + detail, result["store_info"]


def handle_create_project(name):
    if not name or not name.strip():
        return "Enter a project name.", gr.update()
    name = name.strip().lower().replace(" ", "-")
    from config import get_project_dir
    get_project_dir(name)
    return f"Project '{name}' created.", gr.update(choices=get_projects_list(), value=name)


# ── CSS ──────────────────────────────────────────────────────────────────────

CSS = """
.gradio-container { max-width: 1200px !important; margin: 0 auto !important; }
.main-header {
    text-align: center;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    padding: 2rem; border-radius: 16px; margin-bottom: 1rem;
    border: 1px solid rgba(255,255,255,0.1);
}
.main-header h1 {
    background: linear-gradient(90deg, #e94560, #533483, #0f3460);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    font-size: 2.4rem !important; margin-bottom: 0.5rem;
}
.main-header p { color: #a0aec0; }
#search-btn { background: linear-gradient(135deg, #e94560, #533483) !important; border: none !important; font-weight: 700 !important; }
#seed-btn { background: linear-gradient(135deg, #10b981, #059669) !important; border: none !important; }
"""


# ── Build UI ─────────────────────────────────────────────────────────────────

def build_ui():
    with gr.Blocks(
        title="ARIA Vision Intelligence",
        theme=gr.themes.Soft(
            primary_hue="indigo", secondary_hue="rose", neutral_hue="slate",
            font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
        ),
        css=CSS,
    ) as app:

        gr.HTML("""
        <div class="main-header">
            <h1>ARIA Vision Intelligence</h1>
            <p>GPU-accelerated multimodal search &mdash; Qwen3-VL + hipVS CAGRA</p>
            <p style="font-size:0.85rem; color:#718096;">
                Create projects &rarr; Upload media &rarr; Direct multimodal embedding &rarr; CAGRA index &rarr; Search &rarr; LLM interpretation
            </p>
        </div>
        """)

        # Project selector (shared across tabs)
        with gr.Row():
            project_select = gr.Dropdown(
                choices=get_projects_list(),
                value=DEFAULT_PROJECT,
                label="Active Project",
                scale=3,
                interactive=True,
            )
            new_project_name = gr.Textbox(label="New Project Name", placeholder="my-project", scale=2)
            create_btn = gr.Button("+ Create", scale=1, size="sm")
            create_status = gr.Textbox(visible=False)

        create_btn.click(
            fn=handle_create_project,
            inputs=[new_project_name],
            outputs=[create_status, project_select],
        )

        with gr.Accordion("System Status", open=False):
            system_info = gr.Markdown(value=get_system_info())
            project_select.change(fn=get_system_info, inputs=[project_select], outputs=[system_info])

        with gr.Tabs():

            # ── Search ──────────────────────────────────────────────────
            with gr.Tab("Search"):
                gr.Markdown("### Semantic Visual Search\nDescribe what you're looking for in natural language.")
                with gr.Row():
                    with gr.Column(scale=4):
                        query_input = gr.Textbox(
                            label="Search Query",
                            placeholder='e.g. "a dog running on the beach"',
                            lines=2,
                        )
                    with gr.Column(scale=1):
                        search_mode = gr.Radio(["Image Search", "Video Intelligence"], value="Image Search", label="Mode")
                        top_k = gr.Slider(1, 50, value=10, step=1, label="Top-K")

                search_btn = gr.Button("Search", variant="primary", elem_id="search-btn", size="lg")
                search_results = gr.Markdown(value="*Enter a query above*")
                store_info = gr.Textbox(label="Store Info", interactive=False, lines=1)

                search_btn.click(fn=handle_search, inputs=[query_input, search_mode, top_k, project_select], outputs=[search_results, store_info])
                query_input.submit(fn=handle_search, inputs=[query_input, search_mode, top_k, project_select], outputs=[search_results, store_info])

            # ── Upload ──────────────────────────────────────────────────
            with gr.Tab("Upload & Ingest"):
                gr.Markdown("### Upload Media\nUpload images or videos. Each is embedded directly (no captioning) and indexed.")
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("#### Images")
                        img_upload = gr.File(label="Upload", file_types=["image"], file_count="multiple")
                        img_btn = gr.Button("Ingest Images")
                        img_log = gr.Textbox(label="Log", lines=8, interactive=False)
                    with gr.Column():
                        gr.Markdown("#### Videos")
                        vid_upload = gr.File(label="Upload", file_types=["video"], file_count="multiple")
                        vid_btn = gr.Button("Ingest Videos")
                        vid_log = gr.Textbox(label="Log", lines=8, interactive=False)

                gr.Markdown("---")
                with gr.Row():
                    seed_btn = gr.Button("Seed from HF Dataset", variant="primary", elem_id="seed-btn")
                    batch_btn = gr.Button("Batch Re-Index", variant="primary")
                    clear_btn = gr.Button("Clear All Indexes", variant="stop")
                action_log = gr.Textbox(label="Action Log", lines=10, interactive=False)

                img_btn.click(fn=handle_image_upload, inputs=[img_upload, project_select], outputs=[img_log, system_info])
                vid_btn.click(fn=handle_video_upload, inputs=[vid_upload, project_select], outputs=[vid_log, system_info])
                seed_btn.click(fn=handle_seed, inputs=[project_select], outputs=[action_log, system_info])
                batch_btn.click(fn=handle_batch_ingest, inputs=[project_select], outputs=[action_log, system_info])
                clear_btn.click(fn=handle_clear, inputs=[project_select], outputs=[action_log, system_info])

            # ── About ───────────────────────────────────────────────────
            with gr.Tab("About"):
                gr.Markdown("""
## How It Works

1. **Create a project** -- each project has isolated sources and indexes
2. **Upload images/videos** -- embedded directly by Qwen3-VL or CLIP (no captioning)
3. **CAGRA rebuilds** on every insert -- optimized for query speed
4. **Search** -- your query is embedded by the same model, matched via CAGRA in microseconds
5. **LLM interprets** -- Qwen3-35B-A3B summarizes the raw results

### Models

| Role | GPU | CPU |
|------|-----|-----|
| Embedding | Qwen3-VL-Embedding-2B/8B | CLIP ViT-L/14 |
| LLM | Qwen3-35B-A3B (MoE, 3B active) | Qwen3-1.7B / HF API |

### GPU Tiers

| Tier | Backend | Latency |
|------|---------|---------|
| 1 | CAGRA (hipVS) | ~50 us |
| 2 | PyTorch hipBLAS | ~2 ms |
| 3 | NumPy CPU | ~15 ms |

### Memory Management

Indexes live on NVMe as `.cagra` files. When a project is queried, its index is
async-copied into VRAM via pinned-memory DMA. Idle indexes are evicted to free
VRAM for active ones. This lets dozens of projects share a single GPU.

---
*Built for the AMD Hackathon*
                """)

    return app


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if seed_data.is_needed():
        logger.info("Auto-seeding default project from HF Dataset...")
        seed_data.run()

    app = build_ui()
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)
