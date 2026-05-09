"""
Kairos AI — Full Pipeline End-to-End Test
Tests: dispatch → triage → orchestrator (with calls) → closer → simulation
"""
import urllib.request
import json
import time
import uuid
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

BASE = "http://localhost:8000"


def post(url, data=None):
    if data:
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def main():
    print("=" * 60)
    print("  KAIROS AI — Full Pipeline Test")
    print("=" * 60)

    # 1. Health
    print("\n1. Health check...")
    h = get(f"{BASE}/health")
    print(f"   {h}")

    # 2. Driver check
    print("\n2. Driver dashboard (pre-dispatch)...")
    d = get(f"{BASE}/api/driver/AMB-001/dashboard")
    print(f"   Status: {d['status']}, Driver: {d['driver_name']}")

    # 3. Create emergency directly in Firestore
    eid = str(uuid.uuid4())
    print(f"\n3. Creating test emergency {eid[:8]}...")
    from app.services.firebase_client import emergencies_ref
    emergencies_ref().document(eid).set({
        "patient_id": None,
        "bystander_lat": 12.9716,
        "bystander_lng": 77.5946,
        "bystander_notes": "Patient collapsed with severe chest pain, sweating profusely, semi-conscious",
        "status": "active",
        "ambulance_id": None,
        "chosen_hospital_id": None,
        "identification_status": "not_identified",
        "routing_status": None,
        "alert_acknowledged": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    print(f"   Emergency created: {eid[:8]}")

    # 4. Dispatch
    print("\n4. Dispatching ambulance...")
    dispatch = post(f"{BASE}/api/emergency/{eid}/dispatch")
    amb = dispatch["assigned_ambulance"]
    print(f"   Ambulance: {amb['id']}")
    print(f"   Driver: {amb['driver_name']}")
    print(f"   ETA: {amb['eta_minutes']} min")
    preps = dispatch.get("prep_instructions", [])
    if preps:
        print(f"   Prep instructions:")
        for p in preps[:3]:
            print(f"     - {p}")

    # 5. Wait for pipeline
    print("\n5. Waiting for auto-route pipeline...")
    print("   (triage → orchestrator → hospital calls → closer → simulation)")
    chosen = None
    for i in range(45):
        time.sleep(2)
        try:
            status = get(f"{BASE}/api/emergency/{eid}/routing-status")
        except Exception:
            continue
        rs = status.get("routing_status", "pending")
        hc = len(status.get("hospitals_checked", []))
        ch = status.get("chosen_hospital")

        if i % 3 == 0:
            print(f"   [{i*2:3d}s] routing_status={rs}, hospitals_checked={hc}", end="")
            if ch:
                print(f", chosen={ch['name']}")
            else:
                print()

        if rs == "routing_complete" and ch:
            chosen = ch
            print(f"\n   ✅ HOSPITAL SELECTED: {ch['name']}")
            if ch.get("reason"):
                print(f"   📝 Reason: {ch['reason']}")
            break

    if not chosen:
        print("\n   ❌ Pipeline did not complete in 90 seconds")
        # Check backend logs
        print("   Check backend terminal for error details")
    else:
        # 6. Driver dashboard post-routing
        print(f"\n6. Driver dashboard (post-routing)...")
        d2 = get(f"{BASE}/api/driver/{amb['id']}/dashboard")
        print(f"   Status: {d2['status']}")
        print(f"   Hospital: {d2.get('hospital_name', 'N/A')}")
        print(f"   Hospital Nav: {d2.get('hospital_directions_link', 'N/A')[:60]}...")
        print(f"   Reason: {d2.get('scoring_reason', 'N/A')}")

        # 7. Simulation status
        print(f"\n7. Simulation status...")
        for i in range(15):
            try:
                sim = get(f"{BASE}/api/simulation/status/{eid}")
                phase = sim.get("phase", "waiting")
                status_text = sim.get("status_text", "")
                progress = sim.get("progress_percent", 0)
                print(f"   Phase: {phase}, Progress: {progress}%, Status: {status_text}")
                if phase in ("complete", "arrived"):
                    print(f"\n   ✅ SIMULATION COMPLETE!")
                    break
            except Exception as e:
                print(f"   Error: {e}")
            time.sleep(1)

    print("\n" + "=" * 60)
    print("  PIPELINE TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
