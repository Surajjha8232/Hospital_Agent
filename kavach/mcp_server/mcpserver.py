# mcp/server.py

import faiss
import pickle
import numpy as np
import vertexai
from vertexai.preview.language_models import TextEmbeddingModel
import os
from fastapi import FastAPI
from fastmcp import FastMCP
# from department_lookup import department_lookup
# from doctor_lookup import get_doctors_by_department
# from schedule_lookup import get_doctor_schedule
# from auth import get_access_token
import requests
import time
from threading import Lock
from datetime import datetime
import uuid
from google.cloud import firestore


db = firestore.Client(project="trans-opus-484315-h8",database="hospital-db")
# -----------------------------------------------------------------------------
# Create MCP Server
# -----------------------------------------------------------------------------
mcp = FastMCP(
    name="hospital_mcp_server",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "3333"))
)

app = FastAPI(title="Hospital MCP Server")


PROJECT_ID = "trans-opus-484315-h8"
LOCATION = "us-central1"
EMBEDDING_MODEL = "text-embedding-004"


DOCTOR_LIST_URL = (
    "https://wellness.bhaktivedantahospital.com/"
    "appointmentApi/apptapi/data/doctorlist"
)
SCHEDULE_URL = (
    "https://wellness.bhaktivedantahospital.com/"
    "appointmentApi/apptapi/data/doctorschedule"
)

TOKEN_URL = "https://wellness.bhaktivedantahospital.com/appointmentApi/apptapi/token"
API_KEY = "mpzqo-yAQB_5IygHeqwrDFoH_r3VQu6ZXV66kMb9pG4"

_token_cache = {
    "access_token": None,
    "expires_at": 0
}

_lock = Lock()

def _parse_expires_in(expires_in: str) -> int:
    """
    Converts expires_in like '1h', '30m' to seconds.
    Default fallback: 3600 seconds
    """
    if isinstance(expires_in, str):
        expires_in = expires_in.lower().strip()
        if expires_in.endswith("h"):
            return int(expires_in[:-1]) * 3600
        if expires_in.endswith("m"):
            return int(expires_in[:-1]) * 60

    # fallback
    return 3600

def get_access_token() -> str:
    """
    Returns a valid token.
    Automatically refreshes if expired.
    """
    with _lock:
        now = time.time()

        # Token still valid (keep 60s buffer)
        if (
            _token_cache["access_token"]
            and now < _token_cache["expires_at"] - 60
        ):
            return _token_cache["access_token"]

        # Fetch new token
        response = requests.post(
            TOKEN_URL,
            headers={"x-api-key": API_KEY},
            timeout=10
        )
        response.raise_for_status()

        data = response.json()

        token = data["access_token"]
        expires_in_raw = data.get("expires_in", "1h")
        expires_in_seconds = _parse_expires_in(expires_in_raw)

        _token_cache["access_token"] = token
        _token_cache["expires_at"] = now + expires_in_seconds

        return token

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
def get_doctors_by_department(department_id: str) -> dict:
    """
    Fetch list of doctors for a given department ID.
    MCP Tool: Fetch doctors for a department ID
    """
    token = get_access_token()

    response = requests.post(
        DOCTOR_LIST_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={"deptid": department_id},
        timeout=10
    )

    response.raise_for_status()
    doctors = response.json().get("data", [])

    # Normalize response (VERY IMPORTANT for agent)
    normalized = []
    for d in doctors:
        normalized.append({
            "doctor_id": d["id"],
            "name": f'{d["prefix"]}{d["firstname"]} {d["lastname"]}'.strip(),
            "education": d["education"],
            "specialization": d["specialization"],
            "department": d["department"]
        })

    return {
        "department_id": department_id,
        "total_doctors": len(normalized),
        "doctors": normalized
    }


@mcp.tool()
def get_doctor_schedule(doctor_id: str,start_date: str | None = None) -> dict:
    """
    Fetch available appointment slots for a doctor.
    MCP Tool: Fetch available slots for a doctor (today + next 2 days)
    """

    if not start_date:
        start_date = datetime.utcnow().strftime("%Y-%m-%d")

    token = get_access_token()

    response = requests.post(
        SCHEDULE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "doctorId": int(doctor_id),
            "startDate": start_date
        },
        timeout=10
    )

    response.raise_for_status()
    data = response.json()

    slot_duration = data.get("slotDurationMinutes", 0)
    raw_schedule = data.get("data", {})

    available_schedule = {}

    for date, slots in raw_schedule.items():
        free_slots = [
            {
                "from": s["from"],
                "to": s["to"]
            }
            for s in slots
            if not s.get("booked", True)
        ]

        if free_slots:
            available_schedule[date] = free_slots

    return {
        "doctor_id": doctor_id,
        "slot_duration_minutes": slot_duration,
        "available_dates": available_schedule
    }


@mcp.tool()
def store_confirmed_appointment_tool(
    patient_name: str,
    patient_age: int,
    patient_contact: str,
    patient_address: str,
    doctor_id: str,
    doctor_name: str,
    department_id: str,
    department_name: str,
    appointment_date: str,
    appointment_time: str,
    slot_duration_minutes: int,
    whatsapp_number: str
) -> dict:
    """
    Stores confirmed appointment details in Firestore.
    """
    try:
        appointment_id = f"apt_{uuid.uuid4().hex[:8]}"

        doc = {
            "appointment_id": appointment_id,
            "status": "CONFIRMED",

            "patient": {
                "name": patient_name,
                "age": patient_age,
                "contact_number": patient_contact,
                "address": patient_address
            },

            "doctor": {
                "doctor_id": doctor_id,
                "doctor_name": doctor_name,
                "department_id": department_id,
                "department_name": department_name
            },

            "slot": {
                "date": appointment_date,
                "time": appointment_time,
                "duration_minutes": slot_duration_minutes
            },

        "source": "whatsapp",
        "whatsapp_number": whatsapp_number,
        "created_at": datetime.utcnow().isoformat()
        }

        db.collection("appointments").document(appointment_id).set(doc)
    
    except Exception as e:
        return {
            "status": "error",
             "message": "Unable to store appointment at this moment. Please try again.",
        }

    return {
        "status": "success",
        "appointment_id": appointment_id
    }
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