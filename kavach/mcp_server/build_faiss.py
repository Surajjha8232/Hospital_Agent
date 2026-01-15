import json
import faiss
import numpy as np
import pickle

EMBED_DIM = 768
INPUT_FILE = "departments.jsonl"
INDEX_FILE = "dept.index"
META_FILE = "dept_meta.pkl"

vectors = []
metadata = []

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        vectors.append(d["embedding"])
        metadata.append({
            "id": d["id"],
            "name": d["metadata"]["name"],
            "description": d["metadata"]["description"]
        })

vectors = np.array(vectors).astype("float32")

index = faiss.IndexFlatIP(EMBED_DIM)
faiss.normalize_L2(vectors)
index.add(vectors)

faiss.write_index(index, INDEX_FILE)

with open(META_FILE, "wb") as f:
    pickle.dump(metadata, f)

print(f"✅ FAISS index built with {len(metadata)} departments")
