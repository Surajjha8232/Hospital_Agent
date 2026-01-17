# mcp/schedule_lookup.py

import requests
from datetime import datetime
from auth import get_access_token

SCHEDULE_URL = (
    "https://wellness.bhaktivedantahospital.com/"
    "appointmentApi/apptapi/data/doctorschedule"
)


def get_doctor_schedule(doctor_id: str, start_date: str = None):
    """
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
