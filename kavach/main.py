from fastapi import FastAPI
from agent import root_agent

app = FastAPI()

@app.post("/query")
async def query_agent(user_input: str, user_id: str, session_id: str):
    # This calls your agent directly
    response = root_agent.query(
        input=user_input,
        user_id=user_id,
        session_id=session_id
    )
    return response