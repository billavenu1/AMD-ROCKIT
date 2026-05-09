# vision/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Combine USE_GPU and USING_AMD_GPU into single env var 'USE_GPU'
# Falls back to False if not set
USING_AMD_GPU = os.getenv("USE_GPU", "false").lower() in ("true", "1", "yes")

# Path for NVMe swap files
SWAP_PATH = os.getenv("SWAP_PATH", "/fast_nvme/vector_swap")

# Dimension of embeddings (e.g., 2048 for gemini-embedding-2)
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "2048"))

# How many seconds apart to sample frames for video ingestion
FRAME_EVERY_SEC = int(os.getenv("FRAME_EVERY_SEC", "2"))
