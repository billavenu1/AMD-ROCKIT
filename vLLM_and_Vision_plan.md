# vLLM & Vision Implementation Plan

This document outlines the architecture and execution plan for fully implementing the backend for Model Deployments (via vLLM) and the Vision Page (via SurrealDB vector search).

---

## 1. Architecture: Port Strategy & Endpoint Separation

**The Problem:** Currently, the main FastAPI application runs on port `5055`. Should the vLLM inference server run on the same port?

**The Solution: Separation of Concerns (Port 6000+)**
You should **not** serve vLLM on the same port (5055) as your main application.

* **Main API (Port 5055 - The Control Plane):** Handles UI routing, SurrealDB queries, model management, authentication, RAG logic, and Vision file ingestion.
* **vLLM Inference Server (Port 6000 - The Data Plane):** Dedicated purely to model inference. Running it separately ensures that heavy GPU loads and blocked inference threads do not freeze your main UI/Management API.

**Workflow:**

1. User clicks "Deploy" on the UI (Port 5055).
2. The Main API (5055) executes `vllm_deploy_model(**kwargs)`, which spawns a new vLLM process (or container) on a dedicated port (e.g., `6000`).
3. The Main API saves the new `endpoint: http://localhost:6000/v1` and `api_key` to SurrealDB.
4. Other services (RAG, Agents, NotebookLM) query SurrealDB for the active model's endpoint and communicate directly with `http://localhost:6000`.

---

## 2. Model Catalog & Deployments Implementation

### A. Deploy Endpoint (`POST /api/catalog/deploy`)

When the user clicks "Deploy" from the catalog:

1. **Receive Request:** The API receives `model_id`, `quantization`, and `target_gpu`.
2. **Execute vLLM Deployment:** Call the Python function `vllm_deploy_model(model_id=model_id, quantization=quantization, gpu=target_gpu)`. This function will allocate GPU resources and start the vLLM server on a new port (e.g., 6000).
   *(For now, this will be implemented as a placeholder function that simply returns a success message based on the request, without actually deploying vLLM.)*
3. **Database Write:** Instead of writing to `deployed_models.json`, the function will execute a SurrealDB query:

   ```sql
   CREATE deployment SET 
       model_id = $model_id,
       status = 'Running',
       endpoint = 'http://localhost:6000/v1/chat/completions',
       api_key = $generated_key,
       config = $config;
   ```

### B. Active Deployments Endpoint (`GET /api/deployments`)

When the user navigates to the "Active Deployments" page:

1. The API executes a SurrealDB query: `SELECT * FROM deployment;`
2. It returns a JSON list containing the `model_id`, `status`, `endpoint`, and `api_key` for the UI to display in the table.

---

---

---

# 3. Vision Task & Multi-Modal Embeddings

To make the Vision page demo-ready, we implement a focused ingestion pipeline using `gemini-embedding-2` and SurrealDB vector indexes. The key insight is that `gemini-embedding-2` is a **native multimodal model** — it embeds images, video, and text into the **same unified vector space**, meaning a text query like *"zebra"* and a video frame containing a zebra will have naturally high cosine similarity without any bridging or cross-modal tricks.

---

## A. Embedding Dimensions — Clarification

`gemini-embedding-2` outputs **2048 dimensions by default**, with Matryoshka Representation Learning (MRL) allowing truncation to 1536, 768, or 128 without meaningful quality loss. The recommended sizes are **768, 1536, or 2048**.

For this demo we use **2048** (default, highest quality). If storage becomes a concern, drop to **1536** with one parameter change. The `output_dimensionality` parameter controls this:

```python
config=types.EmbedContentConfig(output_dimensionality=2048)
# or 1536 for half the storage, negligible quality drop
```

All SurrealDB index definitions use `DIMENSION 2048` to match.

---

## B. Ingestion Scripts

Three scripts handle the full pipeline from raw media to indexed embeddings.

### 1. `sample_images_upload.py`

Reads up to 30 images from a local folder and prepares them for embedding.

* Scans a folder for `.jpg`, `.jpeg`, `.png`, `.webp` files (capped at 30)
* Extracts metadata: `file_path`, `file_size` (in KB), `resolution` (e.g. `1920x1080`)
* Reads each image as **raw bytes** and passes directly to `gemini-embedding-2` — no resizing, no base64 encoding, no OpenCV needed. The API handles decoding natively.

```python
from google import genai
from google.genai import types

client = genai.Client()

with open('example.png', 'rb') as f:
    image_bytes = f.read()

result = client.models.embed_content(
    model='gemini-embedding-2',
    contents=[
        types.Part.from_bytes(
            data=image_bytes,
            mime_type='image/png',
        ),
    ],
    config=types.EmbedContentConfig(output_dimensionality=2048)
)

embedding = result.embeddings[0].values  # 2048-dim vector
```

### 2. `sample_video_upload.py`

Processes a 1080p demo video using `gemini-embedding-2`'s **native video embedding** — no frame extraction, no OpenCV, no base64 loops.

**For videos under 120 seconds**, the entire video is passed as raw bytes in a single call:

```python
from google import genai
from google.genai import types

client = genai.Client()

with open('demo_video.mp4', 'rb') as f:
    video_bytes = f.read()

result = client.models.embed_content(
    model='gemini-embedding-2',
    contents=[
        types.Part.from_bytes(
            data=video_bytes,
            mime_type='video/mp4',
        ),
    ],
    config=types.EmbedContentConfig(output_dimensionality=2048)
)

embedding = result.embeddings[0].values  # single 2048-dim vector for the whole clip
```

**For videos over 120 seconds** (which applies to any real demo video), the video is chunked into **overlapping segments** and each chunk is embedded individually. Each chunk becomes one record in `video_index` with its own `timestamp_start`, `timestamp_end`, and `embedding`:

```python
def chunk_video_bytes(video_path: str, chunk_sec: int = 60, overlap_sec: int = 5):
    """
    Split video into overlapping chunks of `chunk_sec` seconds.
    Overlap prevents missing content that falls on a boundary.
    Returns list of {video_bytes, timestamp_start, timestamp_end, timestamp_label}
    """
    import subprocess, tempfile, os

    # Get total duration via ffprobe
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ], capture_output=True, text=True)
    duration = float(probe.stdout.strip())

    chunks = []
    start = 0.0

    while start < duration:
        end = min(start + chunk_sec, duration)

        # Extract chunk using ffmpeg into a temp file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name

        subprocess.run([
            "ffmpeg", "-y", "-i", video_path,
            "-ss", str(start), "-to", str(end),
            "-c", "copy", tmp_path
        ], capture_output=True)

        with open(tmp_path, "rb") as f:
            video_bytes = f.read()
        os.unlink(tmp_path)

        m_s, s_s = divmod(int(start), 60)
        m_e, s_e = divmod(int(end), 60)

        chunks.append({
            "video_bytes":     video_bytes,
            "timestamp_start": start,
            "timestamp_end":   end,
            "timestamp_label": f"{m_s:02d}:{s_s:02d}",
        })

        start += chunk_sec - overlap_sec  # slide forward with overlap

    return chunks
```

Each chunk is then embedded exactly like the short-video example above — `types.Part.from_bytes(data=chunk["video_bytes"], mime_type="video/mp4")`.

### 3. `upload_samples_vision.py` — The Master Script

Orchestrates the full pipeline end-to-end.

* **Initializes** the Gemini client (`genai.Client()`) — single shared instance across all calls
* **Calls** `sample_video_upload.py` to chunk the demo video and embed each chunk
* **Calls** `sample_images_upload.py` to load and embed all sample images
* **Sets up SurrealDB** — defines both tables, all fields, and all indexes before inserting
* **Inserts records** into `video_index` and `image_index` with their embeddings

---

## C. SurrealDB Vector Index Structure

Two tables with MTREE vector indexes. Dimension is **2048** to match `gemini-embedding-2` default output.

### Image Table — `image_index`

| Field        | Type   | Description                             |
| ------------ | ------ | --------------------------------------- |
| `file_path`  | string | Path to the image file                  |
| `file_size`  | string | Size in KB, e.g. `"240KB"`              |
| `resolution` | string | Original resolution, e.g. `"1920x1080"` |
| `embedding`  | array  | 2048-dim float vector                   |

```sql
DEFINE INDEX image_embedding_index ON image_index
    FIELDS embedding
    MTREE DIMENSION 2048
    DIST COSINE;
```

### Video Table — `video_index`

| Field             | Type   | Description                          |
| ----------------- | ------ | ------------------------------------ |
| `video_path`      | string | Path to the source video             |
| `timestamp_start` | float  | Chunk start in seconds, e.g. `120.0` |
| `timestamp_end`   | float  | Chunk end in seconds, e.g. `180.0`   |
| `timestamp_label` | string | Human-readable, e.g. `"02:00"`       |
| `embedding`       | array  | 2048-dim float vector for this chunk |

```sql
DEFINE INDEX video_embedding_index ON video_index
    FIELDS embedding
    MTREE DIMENSION 2048
    DIST COSINE;

-- Secondary index for time-range pre-filtering
DEFINE INDEX video_time_index ON video_index
    FIELDS video_path, timestamp_start;
```

---

## D. Vision Endpoint — `POST /api/vision/chat`

### 1. Receive Query

```json
{ "prompt": "show me the zebra", "mode": "Video Intelligence" }
```

### 2. Embed the Prompt

The text query is embedded using the **same model and same dimension** as the ingested content. This is what makes cross-modal search work — text and video/image embeddings live in the same vector space.

```python
result = client.models.embed_content(
    model="gemini-embedding-2",
    contents="show me the zebra",
    config=types.EmbedContentConfig(output_dimensionality=2048)
)
query_vector = result.embeddings[0].values
```

### 3. Vector Search in SurrealDB

**If `mode == "Video Intelligence"`:**

```sql
SELECT video_path, timestamp_start, timestamp_end, timestamp_label,
  vector::similarity::cosine(embedding, $query_vector) AS score
FROM video_index
WHERE score > 0.6
ORDER BY score DESC LIMIT 5;
```

**If `mode == "Image"`:**

```sql
SELECT file_path, file_size, resolution,
  vector::similarity::cosine(embedding, $query_vector) AS score
FROM image_index
WHERE score > 0.6
ORDER BY score DESC LIMIT 5;
```

### 4. Format Response

**Video Intelligence** — adjacent chunks within a 5-second gap are merged into a single range:

```json
{
  "mode": "Video Intelligence",
  "query": "show me the zebra",
  "matches": [
    { "start": "02:00", "end": "02:07", "score": 0.91 },
    { "start": "03:05", "end": "03:09", "score": 0.87 }
  ]
}
```

**Image** — ranked results returned directly:

```json
{
  "mode": "Image",
  "query": "sunset over water",
  "results": [
    { "file_path": "samples/img_04.jpg", "file_size": "240KB", "resolution": "1920x1080", "score": 0.89 },
    { "file_path": "samples/img_17.jpg", "file_size": "185KB", "resolution": "1280x720",  "score": 0.81 }
  ]
}
```

### 5. Return to UI

The frontend uses `start` to seek the HTML5 video player via Media Fragment URIs (`video.mp4#t=120,127`) and highlights the matched range on the seek bar. For images, results render in a scored grid.

---

just for NOW create an Python function called ingest_sample_vision.py which runs the above Index makers and an another python file called query_vision_image.py and query_vision_video.py to print the answer into the cmd, do 