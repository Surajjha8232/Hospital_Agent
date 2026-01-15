import faiss
import pickle
import numpy as np
import vertexai
from vertexai.preview.language_models import TextEmbeddingModel

PROJECT = "trans-opus-484315-h8"
LOCATION = "us-central1"

vertexai.init(project=PROJECT, location=LOCATION)
model = TextEmbeddingModel.from_pretrained("text-embedding-004")

index = faiss.read_index("dept.index")

with open("dept_meta.pkl", "rb") as f:
    meta = pickle.load(f)

def find_department(user_query: str, top_k=3):
    emb = model.get_embeddings([user_query])[0].values
    vec = np.array([emb]).astype("float32")
    faiss.normalize_L2(vec)

    scores, ids = index.search(vec, top_k)

    results = []
    for i in ids[0]:
        results.append(meta[i])

    return results

print(find_department("I have knee pain"))

# [{'id': '27', 'name': 'ORTHOPAEDICS', 'description': 'bone joint fracture knee pain'}, 
# {'id': '53', 'name': 'PAEDIATRIC ORTHOPAEDICS', 'description': 'bone joint fracture knee pain children infant newborn pediatric'},
#  {'id': '44', 'name': 'GENERAL MEDICINE AND RHEUMATOLOGY', 'description': 'arthritis autoimmune joint pain'}]