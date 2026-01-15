from google.cloud import firestore
import json

db = firestore.Client(project="trans-opus-484315-h8",database="hospital-db")

docs = db.collection("departments").stream()

with open("departments.jsonl", "w") as f:
    for doc in docs:
        d = doc.to_dict()
        record = {
            "id": d["department_id"],
            "embedding": d["embedding"],
            "metadata": {
                "name": d["name"],
                "description": d["description"]
            }
        }
        f.write(json.dumps(record) + "\n")

print("Exported departments.jsonl")
