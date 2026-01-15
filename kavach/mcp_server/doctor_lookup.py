# mcp/doctor_lookup.py

import requests
from auth import get_access_token

DOCTOR_LIST_URL = (
    "https://wellness.bhaktivedantahospital.com/"
    "appointmentApi/apptapi/data/doctorlist"
)


def get_doctors_by_department(dept_id: str):
    """
    MCP Tool: Fetch doctors for a department ID
    """

    token = get_access_token()

    response = requests.post(
        DOCTOR_LIST_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={"deptid": dept_id},
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
        "department_id": dept_id,
        "total_doctors": len(normalized),
        "doctors": normalized
    }
