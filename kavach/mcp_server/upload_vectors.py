from google.cloud import aiplatform
from google.cloud import storage
import json
import tempfile
import os

PROJECT = "trans-opus-484315-h8"
REGION = "us-central1"
INDEX_ID = "2170921937369300992"
BUCKET = "kumarai-dept-vectors"
FILE_NAME = "matching_engine.jsonl"

# Init clients
aiplatform.init(project=PROJECT, location=REGION)
storage_client = storage.Client(project=PROJECT)

index = aiplatform.MatchingEngineIndex(INDEX_ID)

# Download JSONL from GCS
bucket = storage_client.bucket(BUCKET)
blob = bucket.blob(FILE_NAME)

tmp_path = os.path.join(tempfile.gettempdir(), "matching_engine.jsonl")
blob.download_to_filename(tmp_path)
print("Downloaded vectors from GCS")

# Load datapoints
datapoints = []
with open(tmp_path, "r", encoding="utf-8") as f:
    for line in f:
        datapoints.append(json.loads(line))

os.unlink(tmp_path)

print(f"Loaded {len(datapoints)} department vectors")

# Upload to Matching Engine
index.upsert_datapoints(datapoints)

print("✅ All department vectors uploaded to Matching Engine")
