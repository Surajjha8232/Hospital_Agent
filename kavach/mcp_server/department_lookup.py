# mcp/department_lookup.py

import faiss
import pickle
import numpy as np
import vertexai
from vertexai.preview.language_models import TextEmbeddingModel

PROJECT_ID = "trans-opus-484315-h8"
LOCATION = "us-central1"
EMBEDDING_MODEL = "text-embedding-004"

# Init Vertex
vertexai.init(project=PROJECT_ID, location=LOCATION)
embedding_model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)

# Load FAISS index + metadata
index = faiss.read_index("dept.index")

with open("dept_meta.pkl", "rb") as f:
    DEPT_META = pickle.load(f)


def department_lookup(user_query: str, top_k: int = 3):
    """
    MCP Tool: Find best matching department from free-text query
    """

    # 1. Embed user query
    embedding = embedding_model.get_embeddings([user_query])[0].values
    vector = np.array([embedding]).astype("float32")
    faiss.normalize_L2(vector)

    # 2. Search FAISS
    scores, indices = index.search(vector, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        dept = DEPT_META[idx]
        results.append({
            "department_id": dept["id"],
            "department_name": dept["name"],
            "confidence": float(score)
        })

    return {
        "query": user_query,
        "best_match": results[0],
        "alternatives": results[1:]
    }

