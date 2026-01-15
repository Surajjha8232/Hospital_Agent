import os
from google.cloud import aiplatform
import vertexai
from hospital_agent.agent import agent_app # Import your agent instance
# Use the class directly from the module if aiplatform.ReasoningEngine is shy
from vertexai.preview import reasoning_engines


# 1. Configuration
PROJECT_ID = "kumaraiagent"
LOCATION = "us-central1"
STAGING_BUCKET = "gs://kumaraiagent-reasoning-engine-staging"
#STAGING_BUCKET = f"gs://{PROJECT_ID}-vertex-staging"

aiplatform.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)
vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)
# 2. Deploy to Reasoning Engine
print("Deploying agent to Vertex AI Reasoning Engine...")

# ADK Agents are compatible with Reasoning Engine deployment
# remote_agent = aiplatform.ReasoningEngine.create(
#     root_agent,
#     requirements=[
#         "google-adk",
#         "requests",
#         "python-dotenv",
#         "zoneinfo"
#     ],
#     display_name="Hospital_Appointment_Agent",
#     description="Agent for hospital appointment booking via MCP"
# )

#agent_app = reasoning_engines.AdkApp(agent=root_agent)

# Then in your deployment call:
remote_agent = reasoning_engines.ReasoningEngine.create(
    agent_app,
    extra_packages=["./hospital_agent"],
    requirements=[
       "google-adk>=1.20.0",  # High version includes critical fixes
        "google-cloud-aiplatform[adk,agent_engines,preview]>=1.75.0",
        "cloudpickle==3.0.0",
        "requests",
        "python-dotenv",
        "pydantic>=2.0.0"
    ],
    display_name="Hospital_Appointment_Agent",
)
print(f"Deployment complete! Resource Name: {remote_agent.resource_name}")