"""Quick Firestore data check."""
from app.services.firebase_client import emergencies_ref, ambulances_ref, users_ref

print("=== ACTIVE EMERGENCIES ===")
for doc in emergencies_ref().stream():
    e = doc.to_dict()
    if e.get("status") in ["active", "routed", "bed_confirmed"]:
        print(f"  ID: {doc.id}")
        print(f"  patient_id: {e.get('patient_id')}")
        print(f"  ambulance_id: {e.get('ambulance_id')}")
        print(f"  status: {e.get('status')}")
        print(f"  identification_status: {e.get('identification_status')}")
        print(f"  routing_status: {e.get('routing_status')}")
        print()

print("=== AMBULANCES ===")
for doc in ambulances_ref().stream():
    a = doc.to_dict()
    print(f"  {doc.id}: status={a.get('status')}")

print("\n=== REGISTERED USERS ===")
for doc in users_ref().stream():
    u = doc.to_dict()
    has_emb = bool(u.get("embedding_json") or u.get("embedding"))
    print(f"  {doc.id}: name={u.get('name')}, has_embedding={has_emb}")
