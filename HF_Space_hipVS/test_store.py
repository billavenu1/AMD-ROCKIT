"""Smoke test for multi-project vector store."""
import sys
import numpy as np
sys.path.insert(0, "HF_Space_hipVS")

from vector_store import get_store, list_projects, VectorStore

# Test multi-project isolation
DIM = 768  # CLIP dim for CPU

store_a = get_store("project-alpha", "image_index")
store_b = get_store("project-beta", "image_index")

vecs_a = np.random.randn(30, DIM).astype(np.float32)
vecs_b = np.random.randn(50, DIM).astype(np.float32)

store_a.add(vecs_a, [f"alpha_{i}" for i in range(30)])
store_b.add(vecs_b, [f"beta_{i}" for i in range(50)])

print(f"Store A: {store_a}")
print(f"Store B: {store_b}")

# Search in A should not return B's vectors
query = np.random.randn(DIM).astype(np.float32)
results_a = store_a.search(query, top_k=3)
results_b = store_b.search(query, top_k=3)

print(f"Search A: {[r['id'] for r in results_a]}")
print(f"Search B: {[r['id'] for r in results_b]}")

# Verify isolation
assert all("alpha" in r["id"] for r in results_a), "Project A returned non-alpha results!"
assert all("beta" in r["id"] for r in results_b), "Project B returned non-beta results!"

# Test append_and_rebuild
store_a.append_and_rebuild(np.random.randn(DIM).astype(np.float32), "alpha_new", {"test": True})
print(f"After append_and_rebuild: {store_a}")

# Test persistence
store_c = get_store("project-alpha", "image_index")  # should be cached
assert store_c.count == 31
print(f"Cached store same ref: {store_c is store_a}")

# List projects
print(f"Projects: {list_projects()}")

# Cleanup
store_a.clear()
store_b.clear()
print("All tests passed")
