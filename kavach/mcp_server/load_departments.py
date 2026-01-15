import requests
import time
from datetime import datetime

from google.cloud import firestore
import vertexai
from vertexai.preview.language_models import TextEmbeddingModel

# ================= CONFIG =================
PROJECT_ID = "trans-opus-484315-h8"
LOCATION = "us-central1"

DEPARTMENT_API = (
    "https://wellness.bhaktivedantahospital.com/appointmentApi/apptapi/data/departmentlist"
)

BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzeXN0ZW0iOiJpbnRlcm5hbC1zZXJ2aWNlIiwic2NvcGUiOiJyZWFkOnBhdGllbnQiLCJpYXQiOjE3Njg0MjQ4MjMsImV4cCI6MTc2ODQyODQyM30.kX91EXDu8x5qDwwHy13jouUu6wIbM7t5L6SN9ixgO-Q"  # 🔐 keep in env var in prod

EMBEDDING_MODEL_NAME = "text-embedding-004"  # 768 dims

# ================= INIT =================
vertexai.init(project=PROJECT_ID, location=LOCATION)

db = firestore.Client(project=PROJECT_ID,database="hospital-db")
embedding_model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL_NAME)

# ================= ENRICHMENT =================
def enrich_description(dept_name: str) -> str:
    name = dept_name.upper()

    rules = {
        "CARDIO": "heart chest pain cardiac blood pressure",
        "CARDIAC": "heart cardiac surgery",
        "ORTHO": "bone joint fracture knee pain",
        "NEURO": "brain nerve spine headache stroke",
        "DERMA": "skin hair nail allergy rash acne",
        "GASTRO": "stomach liver digestion abdominal pain",
        "ENT": "ear nose throat sinus hearing",
        "DENT": "teeth gums oral cavity",
        "GYNAE": "women pregnancy uterus",
        "OBSTET": "pregnancy childbirth delivery",
        "PAEDIATRIC": "children infant newborn pediatric",
        "ONCO": "cancer tumor chemotherapy radiation",
        "PSYCH": "mental health depression anxiety",
        "DIABET": "diabetes blood sugar endocrine",
        "ENDO": "hormone thyroid metabolism",
        "RADIO": "xray ct mri ultrasound imaging",
        "SURGERY": "surgical operation procedure",
        "URO": "kidney bladder prostate urine",
        "NEPHRO": "kidney dialysis renal",
        "HEMATO": "blood disorder anemia",
        "PULMON": "lung breathing respiratory",
        "PHYSIO": "rehabilitation therapy",
        "VASCULAR": "blood vessels circulation",
        "RHEUM": "arthritis autoimmune joint pain",
        "PAIN": "chronic pain management",
    }

    return " ".join(v for k, v in rules.items() if k in name)


# ================= FETCH WITH BEARER =================
headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Accept": "application/json",
}

response = requests.post(DEPARTMENT_API, headers=headers, timeout=30)
response.raise_for_status()

departments = response.json()["data"]
print(f"📥 Fetched {len(departments)} departments")

# ================= STORE =================
BATCH_SIZE = 5
SLEEP_SECONDS = 2

# Filter out empty or invalid departments first
valid_departments = []
for dept in departments:
    name = dept["departmentname"].strip().upper()
    if not name:
        continue
    valid_departments.append(dept)

total_depts = len(valid_departments)
print(f"🔄 Processing {total_depts} valid departments in batches of {BATCH_SIZE}...")

# Process in batches
for i in range(0, total_depts, BATCH_SIZE):
    batch = valid_departments[i : i + BATCH_SIZE]
    batch_inputs = []
    batch_docs = []

    # Prepare batch
    for dept in batch:
        dept_id = str(dept["id"])
        name = dept["departmentname"].strip().upper()
        description = enrich_description(name)
        text_input = f"{name}. {description}".strip()
        
        batch_inputs.append(text_input)
        batch_docs.append({
            "department_id": dept_id,
            "name": name,
            "description": description,
            "active": True,
            "created_at": datetime.utcnow().isoformat()
        })

    try:
        # Get embeddings for the whole batch
        embeddings = embedding_model.get_embeddings(batch_inputs)
        
        for doc_data, embedding_obj in zip(batch_docs, embeddings):
            doc_data["embedding"] = embedding_obj.values
            doc_ref = db.collection("departments").document(doc_data["department_id"])
            doc_ref.set(doc_data)
            print(f"  ✅ Stored: {doc_data['name']}")

        print(f"📦 Batch {i//BATCH_SIZE + 1} complete. Sleeping {SLEEP_SECONDS}s...")
        time.sleep(SLEEP_SECONDS)

    except Exception as e:
        print(f"❌ Error processing batch starting at index {i}: {e}")

print("🎉 Department ingestion complete")
