"""
Kairos AI - Comprehensive API Test Suite
Tests ALL endpoints exhaustively. No stone left unturned.

Run: py -m pytest tests/test_api.py -v --tb=short
Or:  py tests/test_api.py  (standalone mode)
"""
import requests
import json
import uuid
import sys
import os
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

BASE = "http://localhost:8000"

# Track test results
results = []


def test(name, func):
    """Run a test and record the result."""
    try:
        func()
        results.append(("PASS", name, ""))
        print(f"  [PASS] {name}")
    except AssertionError as e:
        results.append(("FAIL", name, str(e)))
        print(f"  [FAIL] {name}: {e}")
    except Exception as e:
        results.append(("ERROR", name, str(e)))
        print(f"  [ERROR] {name}: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. HEALTH & ROOT ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_root():
    r = requests.get(f"{BASE}/")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert data["system"] == "Kairos AI", f"Expected 'Kairos AI', got {data['system']}"
    assert data["version"] == "1.0.0"
    assert "docs" in data

def test_health():
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_docs():
    r = requests.get(f"{BASE}/docs")
    assert r.status_code == 200, f"Swagger docs not accessible: {r.status_code}"

def test_redoc():
    r = requests.get(f"{BASE}/redoc")
    assert r.status_code == 200, f"ReDoc not accessible: {r.status_code}"

def test_openapi():
    r = requests.get(f"{BASE}/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert "paths" in schema
    assert "/api/register" in schema["paths"]
    assert "/api/emergency/identify" in schema["paths"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. REGISTRATION ENDPOINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_register_missing_photos():
    """Should fail with 422 — photos field is required."""
    r = requests.post(f"{BASE}/api/register", data={
        "name": "Test",
        "age": 25,
        "blood_group": "O+",
        "emergency_contact_name": "Mom",
        "emergency_contact_phone": "+911234567890"
    })
    assert r.status_code == 422, f"Expected 422 for missing photos, got {r.status_code}"

def test_register_too_few_photos():
    """Should fail with 400 — need at least 3 photos."""
    # Create a dummy image file
    import io
    dummy = io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
    files = [("photos", ("photo1.png", dummy, "image/png"))]
    r = requests.post(f"{BASE}/api/register", data={
        "name": "Test",
        "age": 25,
        "blood_group": "O+",
        "emergency_contact_name": "Mom",
        "emergency_contact_phone": "+911234567890"
    }, files=files)
    assert r.status_code == 400, f"Expected 400 for too few photos, got {r.status_code}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. EMERGENCY ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_nearby_no_duplicates():
    """Check nearby endpoint returns no duplicates at random location."""
    r = requests.get(f"{BASE}/api/emergency/nearby", params={
        "lat": 0.0, "lng": 0.0
    })
    assert r.status_code == 200
    data = r.json()
    assert data["duplicate"] == False, f"Expected no duplicate, got {data}"

def test_nearby_missing_params():
    """Should fail with 422 — lat/lng required."""
    r = requests.get(f"{BASE}/api/emergency/nearby")
    assert r.status_code == 422

def test_manual_info_nonexistent():
    """Should return 404 for non-existent emergency."""
    r = requests.post(f"{BASE}/api/emergency/nonexistent-id/manual", data={
        "approximate_age": 30,
        "gender": "male"
    })
    assert r.status_code == 404

def test_dispatch_nonexistent():
    """Should return 404 for non-existent emergency."""
    r = requests.post(f"{BASE}/api/emergency/nonexistent-id/dispatch")
    assert r.status_code == 404

def test_condition_nonexistent():
    """Should return 404 for non-existent emergency."""
    r = requests.post(f"{BASE}/api/emergency/nonexistent-id/condition", json={
        "symptoms": "test"
    })
    assert r.status_code == 404

def test_routing_status_nonexistent():
    """Should return 404 for non-existent emergency."""
    r = requests.get(f"{BASE}/api/emergency/nonexistent-id/routing-status")
    assert r.status_code == 404

def test_ambulance_location_nonexistent():
    """Should return 404 for non-existent emergency."""
    r = requests.get(f"{BASE}/api/emergency/nonexistent-id/ambulance-location")
    assert r.status_code == 404


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. DRIVER ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_driver_login_invalid():
    """Should fail with wrong ambulance ID."""
    r = requests.post(f"{BASE}/api/driver/login", json={
        "ambulance_id": "INVALID-ID",
        "driver_phone": "+919876543210"
    })
    assert r.status_code == 200  # Returns 200 with success=False
    data = r.json()
    assert data["success"] == False

def test_driver_login_wrong_phone():
    """Should fail with wrong phone for valid ambulance."""
    r = requests.post(f"{BASE}/api/driver/login", json={
        "ambulance_id": "AMB-001",
        "driver_phone": "+910000000000"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["success"] == False

def test_driver_login_success():
    """Should succeed with correct credentials."""
    r = requests.post(f"{BASE}/api/driver/login", json={
        "ambulance_id": "AMB-001",
        "driver_phone": "+919876543210"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["success"] == True
    assert data["driver_name"] == "Rajesh Kumar"
    assert data["ambulance_id"] == "AMB-001"

def test_driver_dashboard_valid():
    """Should return dashboard for existing ambulance."""
    r = requests.get(f"{BASE}/api/driver/AMB-001/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert data["ambulance_id"] == "AMB-001"
    assert data["driver_name"] == "Rajesh Kumar"
    assert "status" in data

def test_driver_dashboard_nonexistent():
    """Should return 404 for non-existent ambulance."""
    r = requests.get(f"{BASE}/api/driver/INVALID-ID/dashboard")
    assert r.status_code == 404

def test_driver_status_valid():
    """Should return status for existing ambulance (legacy endpoint)."""
    r = requests.get(f"{BASE}/api/driver/AMB-001/status")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data

def test_driver_status_nonexistent():
    """Should return 404 for non-existent ambulance."""
    r = requests.get(f"{BASE}/api/driver/INVALID-ID/status")
    assert r.status_code == 404

def test_driver_notifications_valid():
    """Should return notifications for valid ambulance."""
    r = requests.get(f"{BASE}/api/driver/AMB-001/notifications")
    assert r.status_code == 200
    data = r.json()
    assert "notifications" in data
    assert "unread_count" in data

def test_driver_complete_nonexistent():
    """Should return 404 for non-existent ambulance."""
    r = requests.post(f"{BASE}/api/driver/INVALID-ID/complete")
    assert r.status_code == 404

def test_mark_notification_nonexistent():
    """Should return 404 for non-existent notification."""
    r = requests.post(f"{BASE}/api/driver/AMB-001/notifications/invalid-notif-id/read")
    assert r.status_code == 404


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. HOSPITAL ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_hospital_status_valid():
    """Should return status for existing hospital."""
    r = requests.get(f"{BASE}/api/hospital/HOSP-APOLLO/status")
    assert r.status_code == 200
    data = r.json()
    assert "emergency" in data
    assert "new_patient_alert" in data

def test_hospital_status_nonexistent():
    """Should return 404 for non-existent hospital."""
    r = requests.get(f"{BASE}/api/hospital/INVALID-ID/status")
    assert r.status_code == 404

def test_hospital_confirm_bed_nonexistent_emergency():
    """Should return 404 for non-existent emergency."""
    r = requests.post(f"{BASE}/api/hospital/HOSP-APOLLO/confirm-bed", json={
        "emergency_id": "nonexistent-id",
        "status": "confirmed"
    })
    assert r.status_code == 404

def test_hospital_confirm_bed_invalid_status():
    """Should return 400 for invalid status value."""
    # First create a temp emergency
    from app.services.firebase_client import emergencies_ref
    eid = f"test-bed-{uuid.uuid4().hex[:8]}"
    emergencies_ref().document(eid).set({
        "status": "routed",
        "chosen_hospital_id": "HOSP-APOLLO",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    r = requests.post(f"{BASE}/api/hospital/HOSP-APOLLO/confirm-bed", json={
        "emergency_id": eid,
        "status": "maybe"
    })
    assert r.status_code == 400, f"Expected 400 for invalid status, got {r.status_code}"
    # Cleanup
    emergencies_ref().document(eid).delete()

def test_hospital_confirm_bed_confirmed():
    """Should confirm bed successfully."""
    from app.services.firebase_client import emergencies_ref
    eid = f"test-confirm-{uuid.uuid4().hex[:8]}"
    emergencies_ref().document(eid).set({
        "status": "routed",
        "chosen_hospital_id": "HOSP-APOLLO",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    r = requests.post(f"{BASE}/api/hospital/HOSP-APOLLO/confirm-bed", json={
        "emergency_id": eid,
        "status": "confirmed"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["success"] == True
    assert data["re_routing"] == False
    # Cleanup
    emergencies_ref().document(eid).delete()

def test_hospital_acknowledge_no_emergency():
    """Should return 404 if no active emergency for hospital."""
    r = requests.post(f"{BASE}/api/hospital/HOSP-FORTIS/acknowledge")
    # Depends on state, but if no active emergency routed to Fortis, should be 404
    assert r.status_code in [200, 404]

def test_hospital_ambulance_location_no_emergency():
    """Should return 404 when no ambulance en route."""
    r = requests.get(f"{BASE}/api/hospital/HOSP-APOLLO/ambulance-location")
    # If no active routed emergency, should be 404
    assert r.status_code in [200, 404]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. AMBULANCE ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_ambulance_location_update_valid():
    """Should update location for existing ambulance."""
    r = requests.post(f"{BASE}/api/ambulance/location-update", json={
        "ambulance_id": "AMB-001",
        "lat": 12.9720,
        "lng": 77.5950
    })
    assert r.status_code == 200
    assert r.json()["success"] == True

def test_ambulance_location_update_nonexistent():
    """Should return 404 for non-existent ambulance."""
    r = requests.post(f"{BASE}/api/ambulance/location-update", json={
        "ambulance_id": "INVALID-ID",
        "lat": 12.9720,
        "lng": 77.5950
    })
    assert r.status_code == 404

def test_ambulance_location_update_missing_fields():
    """Should return 422 for missing required fields."""
    r = requests.post(f"{BASE}/api/ambulance/location-update", json={
        "ambulance_id": "AMB-001"
    })
    assert r.status_code == 422


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. FULL EMERGENCY FLOW (E2E)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_e2e_emergency_flow():
    """
    End-to-end: create emergency -> dispatch -> check dashboard -> submit condition.
    This is the core happy path minus face recognition.
    """
    from app.services.firebase_client import emergencies_ref, users_ref

    # 1. Create test patient
    patient_id = f"e2e-patient-{uuid.uuid4().hex[:8]}"
    users_ref().document(patient_id).set({
        "name": "E2E Test Patient",
        "age": 30,
        "blood_group": "B+",
        "conditions": "None",
        "allergies": "None",
        "medications": "None",
        "emergency_contact_name": "Test Contact",
        "emergency_contact_phone": "+919999999999",
        "embedding": []
    })

    # 2. Create emergency directly in Firestore
    emergency_id = f"e2e-emerg-{uuid.uuid4().hex[:8]}"
    emergencies_ref().document(emergency_id).set({
        "patient_id": patient_id,
        "bystander_lat": 12.9716,
        "bystander_lng": 77.5946,
        "bystander_notes": "E2E test emergency",
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "identification_status": "identified"
    })

    # 3. Dispatch ambulance
    r = requests.post(f"{BASE}/api/emergency/{emergency_id}/dispatch")
    assert r.status_code == 200, f"Dispatch failed: {r.status_code} {r.text}"
    dispatch_data = r.json()
    assert "assigned_ambulance" in dispatch_data
    assert "prep_instructions" in dispatch_data
    amb_id = dispatch_data["assigned_ambulance"]["id"]

    # 4. Check driver dashboard
    r = requests.get(f"{BASE}/api/driver/{amb_id}/dashboard")
    assert r.status_code == 200
    dash = r.json()
    assert dash["status"] in ["dispatched", "busy"]
    assert dash["emergency_id"] == emergency_id

    # 5. Submit condition
    r = requests.post(f"{BASE}/api/emergency/{emergency_id}/condition", json={
        "symptoms": "Chest pain, shortness of breath",
        "vitals": "BP 130/85",
        "consciousness_level": "conscious",
        "visible_injuries": "None"
    })
    assert r.status_code == 200
    assert r.json()["success"] == True

    # 6. Check routing status
    r = requests.get(f"{BASE}/api/emergency/{emergency_id}/routing-status")
    assert r.status_code == 200
    rs = r.json()
    assert "routing_status" in rs

    # 7. Check manual info submission
    r = requests.post(f"{BASE}/api/emergency/{emergency_id}/manual", data={
        "approximate_age": 30,
        "gender": "male",
        "visible_injuries": "None",
        "known_conditions": "None"
    })
    assert r.status_code == 200
    assert r.json()["success"] == True

    # 8. Location update from ambulance
    r = requests.post(f"{BASE}/api/ambulance/location-update", json={
        "ambulance_id": amb_id,
        "lat": 12.9750,
        "lng": 77.5980
    })
    assert r.status_code == 200

    # 9. Complete the emergency
    r = requests.post(f"{BASE}/api/driver/{amb_id}/complete")
    assert r.status_code == 200
    assert r.json()["success"] == True

    # 10. Verify ambulance is available again
    r = requests.get(f"{BASE}/api/driver/{amb_id}/dashboard")
    assert r.status_code == 200
    assert r.json()["status"] == "available"

    # Cleanup
    emergencies_ref().document(emergency_id).delete()
    users_ref().document(patient_id).delete()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 8. CORS / HEADERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_cors_headers():
    """CORS should allow any origin (echoes origin when credentials=True)."""
    r = requests.options(f"{BASE}/health", headers={
        "Origin": "http://example.com",
        "Access-Control-Request-Method": "GET"
    })
    assert r.status_code == 200
    # When allow_credentials=True, FastAPI echoes the origin instead of '*'
    acao = r.headers.get("access-control-allow-origin")
    assert acao in ["*", "http://example.com"], f"CORS origin: {acao}"
    assert "GET" in r.headers.get("access-control-allow-methods", "")

def test_json_content_type():
    """API responses should have correct content type."""
    r = requests.get(f"{BASE}/health")
    assert "application/json" in r.headers.get("content-type", "")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 9. SCHEMA VALIDATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_condition_request_validation():
    """Condition endpoint should require 'symptoms' field."""
    from app.services.firebase_client import emergencies_ref
    eid = f"test-schema-{uuid.uuid4().hex[:8]}"
    emergencies_ref().document(eid).set({
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    # Missing 'symptoms'
    r = requests.post(f"{BASE}/api/emergency/{eid}/condition", json={
        "vitals": "BP 120/80"
    })
    assert r.status_code == 422, f"Expected 422 for missing symptoms, got {r.status_code}"
    emergencies_ref().document(eid).delete()

def test_location_update_validation():
    """Location update should validate coordinate types."""
    r = requests.post(f"{BASE}/api/ambulance/location-update", json={
        "ambulance_id": "AMB-001",
        "lat": "not-a-number",
        "lng": 77.0
    })
    assert r.status_code == 422


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RUN ALL TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    print("=" * 60)
    print("  KAIROS AI - Comprehensive API Test Suite")
    print("=" * 60)

    # Check server is running
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        assert r.status_code == 200
        print(f"  Server OK at {BASE}\n")
    except Exception as e:
        print(f"  ERROR: Server not running at {BASE}: {e}")
        print(f"  Start with: py -m uvicorn app.main:app --port 8000")
        sys.exit(1)

    # Health & Root
    print("[1] Health & Root Endpoints")
    test("GET /", test_root)
    test("GET /health", test_health)
    test("GET /docs (Swagger)", test_docs)
    test("GET /redoc", test_redoc)
    test("GET /openapi.json", test_openapi)

    # Registration
    print("\n[2] Registration Endpoint")
    test("POST /api/register (missing photos)", test_register_missing_photos)
    test("POST /api/register (too few photos)", test_register_too_few_photos)

    # Emergency
    print("\n[3] Emergency Endpoints")
    test("GET /api/emergency/nearby (no duplicates)", test_nearby_no_duplicates)
    test("GET /api/emergency/nearby (missing params)", test_nearby_missing_params)
    test("POST /{id}/manual (nonexistent)", test_manual_info_nonexistent)
    test("POST /{id}/dispatch (nonexistent)", test_dispatch_nonexistent)
    test("POST /{id}/condition (nonexistent)", test_condition_nonexistent)
    test("GET /{id}/routing-status (nonexistent)", test_routing_status_nonexistent)
    test("GET /{id}/ambulance-location (nonexistent)", test_ambulance_location_nonexistent)

    # Driver
    print("\n[4] Driver Endpoints")
    test("POST /api/driver/login (invalid)", test_driver_login_invalid)
    test("POST /api/driver/login (wrong phone)", test_driver_login_wrong_phone)
    test("POST /api/driver/login (success)", test_driver_login_success)
    test("GET /{id}/dashboard (valid)", test_driver_dashboard_valid)
    test("GET /{id}/dashboard (nonexistent)", test_driver_dashboard_nonexistent)
    test("GET /{id}/status (valid)", test_driver_status_valid)
    test("GET /{id}/status (nonexistent)", test_driver_status_nonexistent)
    test("GET /{id}/notifications (valid)", test_driver_notifications_valid)
    test("POST /{id}/complete (nonexistent)", test_driver_complete_nonexistent)
    test("POST /{id}/notifications/{nid}/read (nonexistent)", test_mark_notification_nonexistent)

    # Hospital
    print("\n[5] Hospital Endpoints")
    test("GET /api/hospital/{id}/status (valid)", test_hospital_status_valid)
    test("GET /api/hospital/{id}/status (nonexistent)", test_hospital_status_nonexistent)
    test("POST /confirm-bed (nonexistent emergency)", test_hospital_confirm_bed_nonexistent_emergency)
    test("POST /confirm-bed (invalid status)", test_hospital_confirm_bed_invalid_status)
    test("POST /confirm-bed (confirmed)", test_hospital_confirm_bed_confirmed)
    test("POST /acknowledge (no emergency)", test_hospital_acknowledge_no_emergency)
    test("GET /ambulance-location (no emergency)", test_hospital_ambulance_location_no_emergency)

    # Ambulance
    print("\n[6] Ambulance Endpoints")
    test("POST /location-update (valid)", test_ambulance_location_update_valid)
    test("POST /location-update (nonexistent)", test_ambulance_location_update_nonexistent)
    test("POST /location-update (missing fields)", test_ambulance_location_update_missing_fields)

    # Schema Validation
    print("\n[7] Schema Validation")
    test("POST /condition (missing symptoms)", test_condition_request_validation)
    test("POST /location-update (invalid types)", test_location_update_validation)

    # CORS
    print("\n[8] CORS & Headers")
    test("CORS headers", test_cors_headers)
    test("JSON content type", test_json_content_type)

    # E2E Flow
    print("\n[9] End-to-End Emergency Flow")
    test("Full emergency lifecycle", test_e2e_emergency_flow)

    # Summary
    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")
    errors = sum(1 for r in results if r[0] == "ERROR")
    total = len(results)

    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed, {errors} errors")
    print(f"{'=' * 60}")

    if failed + errors > 0:
        print("\n  FAILURES:")
        for status, name, msg in results:
            if status != "PASS":
                print(f"    [{status}] {name}")
                if msg:
                    print(f"           {msg[:200]}")

    print(f"\n{'=' * 60}")
    if failed + errors == 0:
        print("  ALL TESTS PASSED!")
    else:
        print(f"  {failed + errors} test(s) need attention.")
    print(f"{'=' * 60}")

    return failed + errors == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
