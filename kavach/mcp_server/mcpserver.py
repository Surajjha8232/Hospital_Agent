import faiss
import pickle
import numpy as np
import vertexai
from vertexai.preview.language_models import TextEmbeddingModel
import os
from fastapi import FastAPI
from fastmcp import FastMCP
import requests
import time
from typing import Optional
from threading import Lock
from datetime import datetime
from zoneinfo import ZoneInfo
import uuid
from google.cloud import firestore
from dotenv import load_dotenv

BASEDIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASEDIR, '.env'))


# -----------------------------------------------------------------------------
# Create MCP Server
# -----------------------------------------------------------------------------

mcp = FastMCP("hospital_mcp_server", host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
app = FastAPI()


PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
DATABASE = os.getenv("DATABASE")

db = firestore.Client(project=PROJECT_ID,database=DATABASE)
# Init Vertex
vertexai.init(project=PROJECT_ID, location=LOCATION)
embedding_model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)

# Load FAISS index + metadata
index = faiss.read_index("dept.index")

with open("dept_meta.pkl", "rb") as f:
    DEPT_META = pickle.load(f) 

DOCTOR_LIST_URL = (
    "https://wellness.bhaktivedantahospital.com/appointmentApi/apptapi/data"
    "/doctorlist"
)
SCHEDULE_URL = (
    "https://wellness.bhaktivedantahospital.com/appointmentApi/apptapi/data"
    "/doctorschedule"
)

PATIENT_URL = (
    "https://wellness.bhaktivedantahospital.com/appointmentApi/apptapi/data"
    "/patientbymobile"
)
TOKEN_URL = "https://wellness.bhaktivedantahospital.com/appointmentApi/apptapi/token"
API_KEY = os.getenv("API_KEY")

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


@mcp.tool()
def get_current_datetime() -> dict:
    """
    MCP Tool: Returns the current date and time in IST.
    This tool is the authoritative source of current time.
    """

    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))

    return {
        "date": now_ist.strftime("%Y-%m-%d"),
        "time": now_ist.strftime("%H:%M:%S"),
        "year": now_ist.year,
        "timezone": "Asia/Kolkata"
    }

@mcp.tool()
def get_patient_by_whatsapp(__user_id__: str) -> dict:
    """
    Fetch patient records using WhatsApp number.
    The WhatsApp number is derived from ADK session user_id.
    """

    try:
        # WhatsApp sends country code, hospital API expects 10 digits
        print("User Id ",__user_id__)
        mobile = __user_id__[-10:]
        print("User WhatsApp No",mobile)
        token = get_access_token()
        response = requests.post(
            PATIENT_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={"mobile": mobile},
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("success") or data.get("count", 0) == 0:
            return {
                "status": "not_found",
                "message": "No existing patient records were found for your mobile number."
            }

        return {
            "status": "success",
            "total_records": data["count"],
            "patients": data["data"]
        }

    except Exception as e:
        return {
            "status": "error",
            "message": "I’m sorry, I couldn’t retrieve your patient details at the moment. Please try again shortly."
        }


@mcp.tool()
def department_lookup(user_query: str, top_k: int = 5):
    """
    MCP Tool: Resolve user query to department intent
    """

    # 1. Embed user query
    embedding = embedding_model.get_embeddings([user_query])[0].values
    vector = np.array([embedding], dtype="float32")
    faiss.normalize_L2(vector)

    # 2. Search FAISS
    scores, indices = index.search(vector, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        dept = DEPT_META[idx]
        results.append({
            "department_id": dept["id"],
            "department_name": dept["name"],
            "confidence": float(score)
        })

    return {
        "query": user_query,
        "best_match": results
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
def get_doctor_schedule(doctor_id: str, start_date: str = "") -> dict:
    """
    Fetch available appointment slots for a doctor.
    MCP Tool: Fetch available slots for a doctor (today + next 2 days)
    """

    if not start_date:
        start_date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
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


if __name__ == "__main__":
    mcp.run(transport="sse")