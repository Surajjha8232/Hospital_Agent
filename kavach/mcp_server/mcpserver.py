# mcp/server.py

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

# -----------------------------------------------------------------------------
# MCP TOOLS
# -----------------------------------------------------------------------------

@mcp.tool()
def department_lookup_tool(query: str) -> dict:
    """
    Find the most relevant hospital department based on user symptoms or query.
    """
    result = department_lookup(query)
    return result


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