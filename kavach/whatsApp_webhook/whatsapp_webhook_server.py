from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse
import requests
import httpx
import json
import os
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import service_account
from dotenv import load_dotenv

app = FastAPI()

BASEDIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASEDIR, '.env'))


# Twilio Configuration
#TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")  # Get from Twilio Console
# TWILIO_ACCOUNT_SID = "ACa04ef5907d3e208cf173c17d7ffdc39a"
# #TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")    # Get from Twilio Console
# TWILIO_AUTH_TOKEN = "4296a28b0b3847b42248a6a6ceafd3e2"
# TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"      # Your sandbox number

# Your Vertex AI Agent Configuration
PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION")
REASONING_ENGINE_ID = os.getenv("REASONING_ENGINE_ID")  # Your agent resource ID

# Replace these with your own values
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")  # same token as in Meta webhook config
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")  # WhatsApp Cloud API access token
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")  # from WhatsApp Business API dashboard

# twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

async def get_access_token():
    """Get Google Cloud access token for API calls"""
    SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
    SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    credentials.refresh(GoogleRequest())
    access_token = credentials.token

    return access_token

async def get_ExistingSession(user_id: str, client: httpx.AsyncClient, access_token: str) -> str:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    existing_session_payload={
        "class_method": "async_list_sessions",
        "input": {
            "user_id": user_id
        }
    }
    session_url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}:query"
    session_list_resp = await client.post(session_url, json=existing_session_payload, headers=headers)
    # Extract the output sessions list
    output = session_list_resp.json().get("output", {})
    sessions = output.get("sessions", [])
    if sessions:
        # Find the session with the latest lastUpdateTime
        latest_session = max(sessions, key=lambda s: s.get("lastUpdateTime", 0))
        session_id = latest_session["id"]
        return session_id
    else:
        return ""

async def query_vertex_ai_agent(message: str, user_id: str, access_token: str) -> str:
    """Query your Vertex AI Agent Engine"""
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient() as client:
            session_id = await get_ExistingSession(user_id, client, access_token)
            print("Existing Session ID:", session_id)
            if(session_id == ""):
                
                # Create session first (or use existing session ID)
                session_payload = {
                    "class_method": "async_create_session",
                    "input": {
                        "user_id": user_id
                    }
                }
                session_url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}:query"
                
                # Create or get session
                session_response = await client.post(session_url, json=session_payload, headers=headers)
                if session_response.status_code == 200:
                    session_data = session_response.json()
                    output = session_data.get("output", {})
                    session_id = output.get("id", user_id)  # fallback to user_id
                else:
                    session_id = user_id  # Fallback
        
            # Query the agent
            query_payload = {
                "class_method": "async_stream_query",
                "input": {
                    "user_id": user_id,
                    "session_id": session_id,
                    "message": message
                }
            }
            
            query_url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}:streamQuery?alt=sse"
            
            response = await client.post(query_url, json=query_payload, headers=headers)
            
            if response.status_code == 200:
                # Parse the agent response
                response_text = response.text
                # Extract actual message from streaming response
                print("Agent Response:", response_text)
                if response_text.strip():
                    return response_text
                else:
                    return "I received your message but couldn't process it right now."
            else:
                return f"Sorry, I'm having technical difficulties. (Error: {response.status_code})"
                    
    except Exception as e:
        print(f"Error querying agent: {e}")
        return "Sorry, I'm having technical difficulties."



async def extract_agent_texts(agent_response_stream):
    texts = []
    for line in agent_response_stream.splitlines():
        try:
            data = json.loads(line)
            parts = data.get("content", {}).get("parts", [])
            for part in parts:
                if "text" in part:
                    texts.append(part["text"])
        except json.JSONDecodeError:
            continue  # Skip invalid JSON lines
    return texts


# 1. Verification endpoint for WhatsApp webhook setup
@app.get("/wbwebhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Verification failed")

# 2. Main webhook endpoint to receive messages
@app.post("/wbwebhook")
async def receive_webhook(request: Request):
    body = await request.json()

    # Log the incoming payload for debugging
    print("Incoming webhook payload:", body)

    try:
        message = body["entry"][0]["changes"][0]["value"]["messages"][0]
        from_number = message["from"]  # sender's phone number
        msg_body = message.get("text", {}).get("body", "")

        print(f"Message received from {from_number}: {msg_body}")
        access_token = await get_access_token()
        # access_token = "ya29.a0AQQ_BDRIMKrgi2UIyMTU8zQgrBvuzRonK_FxbhAfX3QHGsFAaQYS5ziUaWFrv8-9iEYYX3q1oBK_7misxbY4BS2zANksy6Umg37wodDfkmuBDyC1n_1AhJykc-jpf-rc0uR-Zq470S87c-RYJd6VkSdXFesM8s8O3R7UjHVVQ2PRci0sEv1ioLOS7Pl5bUNlPs-LY6rFiFM-LtgaCgYKATkSARESFQHGX2MisLxpQcXJa5OJb_qXgFA3EQ0214"
        agent_response = await query_vertex_ai_agent(msg_body, from_number, access_token)
        extracted_texts = await extract_agent_texts(agent_response)
        final_response = " ".join(extracted_texts)
        #final_response = "Development In Progress"
        # Send an automated reply back
        send_whatsapp_message(
            to=from_number,
            message=final_response
        )

    except (KeyError, IndexError):
        print("Non-message webhook event received")
        pass

    return {"status": "ok"}

# 3. Helper function to send messages using WhatsApp Cloud API
def send_whatsapp_message(to: str, message: str):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }

    response = requests.post(url, headers=headers, json=payload)
    print("Send message response:", response.json())
    return response.json()

# 4. Optional test endpoint to manually send messages
@app.post("/send-demo")
def send_demo_message(to: str):
    """Send a demo message to test WhatsApp Cloud API delivery"""
    response = send_whatsapp_message(to, "Hello! This is a test message from your FastAPI webhook 🚀")
    return {"response": response}

@app.get("/")
def home():
    return {"message": "WhatsApp Webhook running successfully."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
