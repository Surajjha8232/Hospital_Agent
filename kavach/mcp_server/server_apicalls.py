# mcp/server.py

from fastapi import FastAPI
from pydantic import BaseModel
from department_lookup import department_lookup
from doctor_lookup import get_doctors_by_department
from schedule_lookup import get_doctor_schedule


app = FastAPI(title="Hospital_MCP_Server_FAISS")


class DepartmentRequest(BaseModel):
    query: str

class DoctorRequest(BaseModel):
    department_id: str


class ScheduleRequest(BaseModel):
    doctor_id: str
    start_date: str | None = None


@app.post("/mcp/department-lookup")
def lookup_department(req: DepartmentRequest):
    return department_lookup(req.query)


@app.post("/mcp/doctor-lookup")
def lookup_doctors(req: DoctorRequest):
    return get_doctors_by_department(req.department_id)


@app.post("/mcp/schedule-lookup")
def lookup_schedule(req: ScheduleRequest):
    return get_doctor_schedule(req.doctor_id, req.start_date)
