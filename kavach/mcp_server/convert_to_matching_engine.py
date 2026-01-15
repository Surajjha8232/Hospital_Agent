from google.cloud import storage
import json
import tempfile
import os

BUCKET = "kumarai-dept-vectors"
SOURCE_FILE = "departments.jsonl"
TARGET_FILE = "matching_engine.jsonl"

storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET)
blob = bucket.blob(SOURCE_FILE)

tmp_source = os.path.join(tempfile.gettempdir(), "departments.jsonl")
tmp_target = os.path.join(tempfile.gettempdir(), "matching_engine.jsonl")

blob.download_to_filename(tmp_source)

with open(tmp_source, "r", encoding="utf-8") as src, open(tmp_target, "w", encoding="utf-8") as tgt:
    for line in src:
        d = json.loads(line)
        out = {
            "datapoint_id": d["id"],
            "feature_vector": d["embedding"]
        }
        tgt.write(json.dumps(out) + "\n")

# Upload back
target_blob = bucket.blob(TARGET_FILE)
target_blob.upload_from_filename(tmp_target)

os.remove(tmp_source)
os.remove(tmp_target)

print("✅ Converted and uploaded matching_engine.jsonl")
