# mcp/server.py

import faiss
import pickle
import numpy as np
import vertexai
from vertexai.preview.language_models import TextEmbeddingModel
import os
from fastapi import FastAPI
from fastmcp import FastMCP

from department_lookup import department_lookup
from doctor_lookup import get_doctors_by_department
from schedule_lookup import get_doctor_schedule

# -----------------------------------------------------------------------------
# Create MCP Server
# -----------------------------------------------------------------------------
mcp = FastMCP(
    name="hospital_mcp_server",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8080"))
)

app = FastAPI(title="Hospital MCP Server")


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


# -----------------------------------------------------------------------------
# MCP TOOLS
# -----------------------------------------------------------------------------

@mcp.tool()
def get_department_by_userquery(user_query: str) -> dict:
    """
    Find the most relevant hospital department based on user symptoms or query.
    MCP Tool: Find best matching department from free-text query
    """

    # 1. Embed user query
    top_k = 3
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


@mcp.tool()
def get_doctors_by_department_tool(department_id: str) -> dict:
    """
    Fetch list of doctors for a given department ID.
    """
    return get_doctors_by_department(department_id)


@mcp.tool()
def get_doctor_schedule_tool(
    doctor_id: str,
    start_date: str | None = None
) -> dict:
    """
    Fetch available appointment slots for a doctor.
    """
    return get_doctor_schedule(doctor_id, start_date)


# -----------------------------------------------------------------------------
# SSE ENDPOINT (CRITICAL)
# -----------------------------------------------------------------------------

# @app.get("/sse")
# async def sse():
#     """
#     SSE endpoint required by ADK MCPToolset
#     """
#     return await mcp.handle_sse()


# -----------------------------------------------------------------------------
# Health Check (optional but recommended)
# -----------------------------------------------------------------------------

# @app.get("/health")
# def health():
#     return {"status": "ok"}


# =============================================================================
# Run MCP Server
# =============================================================================
if __name__ == "__main__":
    mcp.run(transport="sse")