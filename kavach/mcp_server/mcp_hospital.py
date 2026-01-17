from fastapi import FastAPI
import os
from fastmcp import FastMCP
import psycopg2
from datetime import datetime, timedelta, date
import calendar
from dotenv import load_dotenv

mcp = FastMCP("hospital_mcp_server", host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
app = FastAPI()

BASEDIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASEDIR, '.env'))

# --------------------------------------------------------------------------
# PostgreSQL Connection
# --------------------------------------------------------------------------
pg_conn = None

def get_pg_connection():
    """Establish and return a PostgreSQL DB connection."""
    global pg_conn

    if pg_conn is None or pg_conn.closed:
        try:
            pg_conn = psycopg2.connect(
                host=os.getenv("PG_HOST"),
                port=os.getenv("PG_PORT", "5432"),
                database=os.getenv("PG_DATABASE"),
                user=os.getenv("PG_USER"),
                password=os.getenv("PG_PASSWORD")
            )
            print("✅ Connected to PostgreSQL")
        except Exception as e:
            print(f"❌ PostgreSQL connection error: {e}")
            pg_conn = None

    return pg_conn


# =============================================================================
# 1️⃣ Identify Department From Symptom
# =============================================================================
# SYMPTOM_MAP = {
#     "knee pain": "Orthopaedic",
#     "back pain": "Orthopaedic",
#     "fever": "General Medicine",
#     "cold": "General Medicine",
#     "rash": "Dermatology",
#     "skin allergy": "Dermatology",
#     "chest pain": "Cardiology",
#     "heart pain": "Cardiology",
# }


# @mcp.tool()
# def get_department_by_symptom(symptom: str) -> dict:
#     """
#     Map natural language symptom → department record.
#     """
#     conn = get_pg_connection()
#     if not conn:
#         return {"error": "DB connection failed"}

#     symptom = symptom.lower().strip()
#     dept_name = SYMPTOM_MAP.get(symptom)

#     if not dept_name:
#         return {"error": f"No department mapped for symptom '{symptom}'."}

#     try:
#         with conn.cursor() as cur:
#             cur.execute("SELECT department_id, name FROM departments WHERE LOWER(name)=LOWER(%s);",
#                         (dept_name,))
#             row = cur.fetchone()

#         if not row:
#             return {"error": f"Department '{dept_name}' not found in DB"}

#         return {"department_id": row[0], "department_name": row[1]}

#     except Exception as e:
#         return {"error": str(e)}


# =============================================================================
# 2️⃣ Fetch Doctors by Department
# =============================================================================
@mcp.tool()
def get_doctors_by_department(department_id: int) -> dict:
    """
    Returns list of doctors belonging to a department.
    """
    conn = get_pg_connection()
    if not conn:
        return {"error": "DB connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT doctor_id, name, specialization, experience_years, contact
                FROM doctors
                WHERE department_id = %s;
            """, (department_id,))
            rows = cur.fetchall()

        doctors = []
        for r in rows:
            doctors.append({
                "doctor_id": r[0],
                "name": r[1],
                "specialization": r[2],
                "experience_years": r[3],
                "contact": r[4],
            })

        return {"count": len(doctors), "doctors": doctors}

    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# 3️⃣ Get Doctor Weekly Availability
# =============================================================================
@mcp.tool()
def get_doctor_availability(doctor_id: int) -> dict:
    """Returns weekly availability for a doctor."""
    conn = get_pg_connection()
    if not conn:
        return {"error": "DB connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT day_of_week, start_time, end_time
                FROM doctor_availability
                WHERE doctor_id = %s
                ORDER BY 
                    CASE day_of_week
                        WHEN 'Monday' THEN 1
                        WHEN 'Tuesday' THEN 2
                        WHEN 'Wednesday' THEN 3
                        WHEN 'Thursday' THEN 4
                        WHEN 'Friday' THEN 5
                        WHEN 'Saturday' THEN 6
                        WHEN 'Sunday' THEN 7
                    END;
            """, (doctor_id,))
            rows = cur.fetchall()

        availability = []
        for r in rows:
            availability.append({
                "day_of_week": r[0],
                "start_time": str(r[1]),
                "end_time": str(r[2]),
            })

        return {"doctor_id": doctor_id, "availability": availability}

    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# Helper: Generate 30–35 minute slots
# =============================================================================
def generate_slots(start, end, slot_minutes=35):
    slots = []
    current = datetime.combine(date.today(), start)
    end_dt = datetime.combine(date.today(), end)

    while current + timedelta(minutes=slot_minutes) <= end_dt:
        slots.append(current.time().strftime("%H:%M"))
        current += timedelta(minutes=slot_minutes)

    return slots


# =============================================================================
# 4️⃣ Get Available Slots for a Doctor on a Date
# =============================================================================
@mcp.tool()
def get_doctor_available_slots(doctor_id: int, appointment_date: str) -> dict:
    """
    Returns available time slots for a doctor on a specific date.
    """
    conn = get_pg_connection()
    if not conn:
        return {"error": "DB connection failed"}

    try:
        appointment_day = calendar.day_name[datetime.strptime(appointment_date, "%Y-%m-%d").weekday()]

        with conn.cursor() as cur:
            cur.execute("""
                SELECT start_time, end_time
                FROM doctor_availability
                WHERE doctor_id = %s AND day_of_week = %s;
            """, (doctor_id, appointment_day))
            availability = cur.fetchone()

        if not availability:
            return {"error": f"Doctor not available on {appointment_day}"}

        start_time, end_time = availability

        # Generate all slots
        all_slots = generate_slots(start_time, end_time)

        # Fetch booked slots
        with conn.cursor() as cur:
            cur.execute("""
                SELECT appointment_time
                FROM appointments
                WHERE doctor_id = %s AND appointment_date = %s AND status='Scheduled';
            """, (doctor_id, appointment_date))
            booked = cur.fetchall()

        booked_slots = {b[0].strftime("%H:%M") for b in booked}
        free_slots = [s for s in all_slots if s not in booked_slots]

        return {
            "doctor_id": doctor_id,
            "appointment_date": appointment_date,
            "available_slots": free_slots
        }

    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# 5️⃣ Get Available Slots for All Doctors in a Department
# =============================================================================
@mcp.tool()
def get_all_doctors_available_slots(department_id: int, appointment_date: str) -> dict:
    """
    Returns available slots for all doctors in a department.
    """
    doctors = get_doctors_by_department(department_id)
    if "error" in doctors:
        return doctors

    result = []

    for doc in doctors["doctors"]:
        slots = get_doctor_available_slots(doc["doctor_id"], appointment_date)
        result.append({
            "doctor_id": doc["doctor_id"],
            "doctor_name": doc["name"],
            "available_slots": slots.get("available_slots", [])
        })

    return {"department_id": department_id, "date": appointment_date, "doctors": result}


# =============================================================================
# 6️⃣ Create Patient
# =============================================================================
@mcp.tool()
def create_patient(name: str, age: int, blood_group: str, address: str,
                   location: str, contact_number: str) -> dict:

    conn = get_pg_connection()
    if not conn:
        return {"error": "DB connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO patients (name, age, blood_group, address, location, contact_number)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING patient_id;
            """, (name, age, blood_group, address, location, contact_number))

            pid = cur.fetchone()[0]

        conn.commit()
        return {"status": "success", "patient_id": pid}

    except Exception as e:
        conn.rollback()
        return {"error": str(e)}


# =============================================================================
# 7️⃣ Book Appointment
# =============================================================================
@mcp.tool()
def book_appointment(patient_id: int, doctor_id: int,
                     appointment_date: str, appointment_time: str) -> dict:

    conn = get_pg_connection()
    if not conn:
        return {"error": "DB connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time)
                VALUES (%s, %s, %s, %s)
                RETURNING appointment_id;
            """, (patient_id, doctor_id, appointment_date, appointment_time))

            appt_id = cur.fetchone()[0]

        conn.commit()
        return {"status": "success", "appointment_id": appt_id}

    except Exception as e:
        conn.rollback()
        return {"error": str(e)}


# =============================================================================
# 8️⃣ Cancel Appointment
# =============================================================================
@mcp.tool()
def cancel_appointment(appointment_id: int) -> dict:
    conn = get_pg_connection()
    if not conn:
        return {"error": "DB connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE appointments
                SET status='Cancelled'
                WHERE appointment_id = %s;
            """, (appointment_id,))

        conn.commit()
        return {"status": "cancelled", "appointment_id": appointment_id}

    except Exception as e:
        conn.rollback()
        return {"error": str(e)}


# =============================================================================
# Run MCP Server
# =============================================================================
if __name__ == "__main__":
    mcp.run(transport="sse")