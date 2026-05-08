"""
Kairos AI — Full Emergency Flow Test
Creates an emergency directly in Firestore, dispatches ambulance,
submits symptoms → triggers AI agents → checks driver dashboard.
"""
import requests
import json
import time
import uuid
import sys
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from app.services.firebase_client import emergencies_ref, users_ref

BASE = "http://localhost:8000"


def main():
    print("=" * 60)
    print("  KAIROS AI - FULL EMERGENCY FLOW TEST")
    print("=" * 60)

    # Step 0: Seed a test patient (so face ID has someone to match)
    print("\n[0] Creating test patient in Firestore...")
    test_patient_id = "test-patient-001"
    users_ref().document(test_patient_id).set({
        "name": "Rahul Kumar",
        "age": 34,
        "blood_group": "O+",
        "conditions": "Cardiac arrhythmia, Hypertension",
        "allergies": "Penicillin",
        "medications": "Metoprolol 50mg daily, Aspirin 75mg",
        "emergency_contact_name": "Priya Kumar",
        "emergency_contact_phone": "+919876543299",
        "embedding": []  # No face embedding for test
    })
    print("    Created patient: Rahul Kumar (O+, Cardiac arrhythmia)")

    # Step 1: Create emergency directly in Firestore
    print("\n[1] Creating emergency record...")
    emergency_id = str(uuid.uuid4())
    emergencies_ref().document(emergency_id).set({
        "patient_id": test_patient_id,
        "bystander_lat": 12.9716,
        "bystander_lng": 77.5946,
        "bystander_notes": "Man collapsed on road, chest pain, semi-conscious",
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "identification_status": "identified"
    })
    print(f"    Emergency ID: {emergency_id}")

    # Step 2: Dispatch ambulance
    print("\n[2] Dispatching ambulance...")
    r = requests.post(f"{BASE}/api/emergency/{emergency_id}/dispatch")
    print(f"    Status: {r.status_code}")
    resp = r.json()
    print(f"    Ambulance: {resp.get('ambulance_id', 'N/A')}")
    print(f"    ETA: {resp.get('eta_minutes', 'N/A')} min")

    # Step 3: Check driver dashboard (should show dispatch alert)
    print("\n[3] Driver dashboard (post-dispatch)...")
    r = requests.get(f"{BASE}/api/driver/AMB-001/dashboard")
    dash = r.json()
    print(f"    Driver: {dash['driver_name']}")
    print(f"    Status: {dash['status']}")
    print(f"    Emergency: {dash.get('emergency_id', 'None')}")
    if dash.get("patient"):
        p = dash["patient"]
        print(f"    Patient: {p.get('name')} | Blood: {p.get('blood_group')} | Conditions: {p.get('conditions')}")
    if dash.get("pickup_directions_link"):
        print(f"    Pickup Nav: {dash['pickup_directions_link'][:90]}...")

    # Step 4: Submit condition (TRIGGERS AI AGENTS)
    print("\n[4] Submitting condition (triggers Triage + Orchestrator agents)...")
    r = requests.post(f"{BASE}/api/emergency/{emergency_id}/condition", json={
        "symptoms": "Severe chest pain radiating to left arm, shortness of breath, profuse sweating",
        "vitals": "BP: 85/55, Pulse: 120, SpO2: 89%",
        "consciousness_level": "semi-conscious",
        "visible_injuries": "None visible"
    })
    print(f"    Status: {r.status_code}")
    print(f"    Response: {r.json().get('message', '')}")

    # Step 5: Wait for AI agents to complete
    print("\n[5] Waiting for AI agents...")
    for i in range(20, 0, -1):
        time.sleep(1)
        # Check if routing is done
        r = requests.get(f"{BASE}/api/emergency/{emergency_id}/routing-status")
        rs = r.json()
        status = rs.get("routing_status", "pending")
        if "complete" in str(status).lower() or rs.get("chosen_hospital"):
            print(f"    Routing complete after {20 - i + 1}s!")
            break
        print(f"    [{i}s] Status: {status}")
    else:
        print("    Timeout - checking results anyway...")

    # Step 6: Check routing result
    print("\n[6] Routing result...")
    r = requests.get(f"{BASE}/api/emergency/{emergency_id}/routing-status")
    rs = r.json()
    print(f"    Routing Status: {rs.get('routing_status', 'N/A')}")
    chosen = rs.get("chosen_hospital")
    if chosen:
        print(f"    Chosen Hospital: {chosen.get('name', 'N/A')}")

    # Step 7: Final driver dashboard
    print("\n[7] Driver dashboard (post-routing)...")
    r = requests.get(f"{BASE}/api/driver/AMB-001/dashboard")
    dash = r.json()
    print(f"    Status: {dash['status']}")
    print(f"    Hospital: {dash.get('hospital_name', 'Still routing...')}")
    print(f"    Hospital Address: {dash.get('hospital_address', 'N/A')}")
    print(f"    Hospital Phone: {dash.get('hospital_phone', 'N/A')}")
    if dash.get("hospital_directions_link"):
        print(f"    Hospital Nav: {dash['hospital_directions_link'][:90]}...")
    print(f"    Scoring Reason: {dash.get('scoring_reason', 'pending')}")
    if dash.get("prep_instructions"):
        print(f"    Prep Instructions: {dash['prep_instructions'][:3]}")

    # Step 8: Driver notifications
    print("\n[8] Driver notifications...")
    r = requests.get(f"{BASE}/api/driver/AMB-001/notifications")
    notifs = r.json()
    print(f"    Unread: {notifs['unread_count']}")
    for n in notifs["notifications"][:5]:
        print(f"    [{n['type']}] {n['title']}")
        if n.get("navigation_link"):
            print(f"      Nav: {n['navigation_link'][:80]}...")

    print("\n" + "=" * 60)
    print("  TEST COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    main()
