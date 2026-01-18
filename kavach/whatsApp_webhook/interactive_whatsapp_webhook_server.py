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


VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")  # same token as in Meta webhook config
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")  # WhatsApp Cloud API access token
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")  # from WhatsApp Business API dashboard
ADK_BASE_URL = os.getenv("ADK_BASE_URL")
APP_NAME = os.getenv("APP_NAME")



async def list_sessions(user_id: str) -> list:
    url = f"{ADK_BASE_URL}/apps/{APP_NAME}/users/{user_id}/sessions"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()

async def create_session(user_id: str) -> str:
    url = f"{ADK_BASE_URL}/apps/{APP_NAME}/users/{user_id}/sessions"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json={})
        resp.raise_for_status()
        data = resp.json()
        print("Created new session id",data["id"])
        return data["id"]

async def get_or_create_session(user_id: str) -> str:
    sessions = await list_sessions(user_id)

    if sessions:
        # pick latest session
        print("existing session id",sessions[-1]["id"])
        return sessions[-1]["id"]

    return await create_session(user_id)

def truncate(text: str, max_len: int) -> str:
    if not text:
        return ""
    return text if len(text) <= max_len else text[: max_len - 1] + "…"

def extract_user_message(message: dict) -> str:
    msg_type = message.get("type")

    # 1️⃣ Normal text
    if msg_type == "text":
        return message.get("text", {}).get("body", "").strip()

    # 2️⃣ Interactive replies
    if msg_type == "interactive":
        interactive = message.get("interactive", {})
        itype = interactive.get("type")

        if itype == "list_reply":
            reply = interactive.get("list_reply", {})
            return json.dumps({
                "selection_type": "list",
                "id": reply.get("id"),
                "title": reply.get("title"),
                "description": reply.get("description")
            })

        if itype == "button_reply":
            reply = interactive.get("button_reply", {})
            return json.dumps({
                "selection_type": "button",
                "id": reply.get("id"),
                "title": reply.get("title")
            })

    return ""

async def extract_final_text_from_adk(adk_response: list) -> str:
    """
    Extract the final user-facing text from ADK /run response.
    """
    # Traverse in reverse — final answer is always at the end
    for event in reversed(adk_response):
        content = event.get("content", {})
        if content.get("role") != "model":
            continue

        parts = content.get("parts", [])
        for part in parts:
            # We want plain text, NOT function calls
            if "text" in part and "functionCall" not in part:
                return part["text"]


    return (
        " ".join(texts)
        if texts
        else "Hare Krishna! 🙏 I’m sorry, I couldn’t retrieve the information just now. Please try again in a moment."
    )

async def extract_agent_payload(adk_response: list) -> dict:
    """
    Extract structured JSON payload returned by the agent.
    """
    for event in reversed(adk_response):
        content = event.get("content", {})
        if content.get("role") != "model":
            continue

        for part in content.get("parts", []):
            if "text" in part:
                try:
                    return json.loads(part["text"])
                except json.JSONDecodeError:
                    # fallback plain text
                    return {
                        "reply_type": "text",
                        "message": part["text"]
                    }

    return {
        "reply_type": "text",
        "message": "Hare Krishna! 🙏 I’m sorry, I couldn’t retrieve the information just now."
    }


async def query_adk_agent(message: str, user_id: str) -> str:
    session_id = await get_or_create_session(user_id)

    payload = {
        "appName": APP_NAME,
        "userId": user_id,
        "sessionId": session_id,
        "newMessage": {
            "role": "user",
            "parts": [
                {"text": message}
            ]
        },
        "streaming": False
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{ADK_BASE_URL}/run",
            json=payload
        )
        resp.raise_for_status()
        return resp.json()



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



from cachetools import TTLCache
processed_message_ids = TTLCache(maxsize=50_000, ttl=300)
# 2. Main webhook endpoint to receive messages
@app.post("/wbwebhook")
async def receive_webhook(request: Request):
    body = await request.json()

    # Log the incoming payload for debugging
    #print("Incoming webhook payload:", body)

    try:
        message = body["entry"][0]["changes"][0]["value"]["messages"][0]
        from_number = message["from"]  # sender's phone number
        #msg_body = message.get("text", {}).get("body", "")
        msg_body = extract_user_message(message)

        if not msg_body:
            print("Empty or unsupported message type received")
            return {"status": "ok"}

        message_id = message["id"]
        if message_id in processed_message_ids:
            print("Duplicate WhatsApp delivery ignored:", message_id)
            return {"status": "ok"}

        processed_message_ids[message_id] = True

        print(f"Message received from {from_number}: {msg_body}")
        agent_response = await query_adk_agent(
            message=msg_body,
            user_id=from_number
        )
        #print("Agent Response : ",agent_response)
        #final_response =  await extract_final_text_from_adk(agent_response)
        #final_response = " ".join(extracted_texts)
        #final_response = "Development In Progress"
        # Send an automated reply back
        agent_payload = await extract_agent_payload(agent_response)

        reply_type = agent_payload.get("reply_type")
        print("Reply Type : ",reply_type)
        if reply_type == "text":
            send_whatsapp_message(
                to=from_number,
                message=agent_payload["message"]
            )

        elif reply_type == "interactive_list":
            send_whatsapp_interactive_list(
                to=from_number,
                interactive=agent_payload
            )

        elif reply_type == "text_with_interactive":
            # 1️ Send text first
            send_whatsapp_message(
                to=from_number,
                message=agent_payload["message"]
            )

            # 2️ Then send interactive
            send_whatsapp_interactive_list(
                to=from_number,
                interactive=agent_payload["interactive"]
            )

        else:
            # Fallback
            send_whatsapp_message(
                to=from_number,
                message="Hare Krishna! 🙏 I’m here to help. Please try again."
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

# 4. Helper function to send interactive list using WhatsApp Cloud API
def send_whatsapp_interactive_list(to: str, interactive: dict):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    rows = [
        {
            "id": item["id"],
            "title":  truncate(item["title"], 24),
            "description": truncate(item.get("description", ""), 72)
        }
        for item in interactive["items"]
    ][:10]

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": interactive["header"]
            },
            "body": {
                "text": interactive["body"]
            },
            "action": {
                "button": interactive["button"],
                "sections": [
                    {
                        "title": "Options",
                        "rows": rows
                    }
                ]
            }
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    print("Interactive send response:", response.json())



# 5. Optional test endpoint to manually send messages
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
