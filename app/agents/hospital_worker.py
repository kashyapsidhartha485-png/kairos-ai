"""
Kairos AI — Hospital Worker
Checks hospital bed availability — single or parallel.
Fresh data → digital check. Stale data → voice call.
PRD Section 7.4
"""
import time
import asyncio
from datetime import datetime, timezone, timedelta
from app.services.firebase_client import (
    hospital_verifications_ref, emergencies_ref
)
from app.agents import voice_agent_v2 as voice_agent


STALENESS_THRESHOLD_MINUTES = 30


async def check(hospital: dict, emergency: dict, emergency_id: str, triage_result: dict) -> dict:
    """
    Check a single hospital for bed availability.
    
    - Fresh data (updated within 30 min): digital check on stored bed counts
    - Stale data: trigger voice agent call
    
    Args:
        hospital: dict with hospital data from Firestore
        emergency: dict with emergency data
        emergency_id: Firestore document ID
        triage_result: parsed triage data
        
    Returns:
        dict with bed_available, method, confidence, hospital info
    """
    hospital_name = hospital.get("name", "Unknown")
    hospital_id = hospital.get("id")
    bed_type_needed = triage_result.get("bed_type_needed", "ICU").lower()

    print(f"[Hospital Worker] Checking {hospital_name}...")

    # Update routing status
    try:
        emergencies_ref().document(emergency_id).update({
            "routing_status": f"checking_{hospital_name.lower().replace(' ', '_')}"
        })
    except Exception:
        pass

    # Check staleness
    last_updated = hospital.get("last_updated")
    is_stale = True

    if last_updated:
        if isinstance(last_updated, str):
            try:
                last_updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            except ValueError:
                last_updated_dt = datetime.min.replace(tzinfo=timezone.utc)
        elif hasattr(last_updated, 'timestamp'):
            # Firestore DatetimeWithNanoseconds
            last_updated_dt = last_updated
        else:
            last_updated_dt = datetime.min.replace(tzinfo=timezone.utc)

        threshold = datetime.now(timezone.utc) - timedelta(minutes=STALENESS_THRESHOLD_MINUTES)
        is_stale = last_updated_dt < threshold

    if not is_stale:
        # ── FRESH DATA: Digital Check ──
        print(f"[Hospital Worker] {hospital_name}: data is FRESH, doing digital check")

        # Check bed availability based on triage bed type
        bed_count = 0
        if "icu" in bed_type_needed:
            bed_count = hospital.get("icu_beds", 0)
        elif "ventilator" in bed_type_needed:
            bed_count = hospital.get("ventilator_beds", 0)
        else:
            bed_count = hospital.get("general_beds", 0)

        bed_available = bed_count > 0

        verification_result = {
            "bed_available": bed_available,
            "method": "digital",
            "confidence": "high",
            "raw_response": f"Digital check: {bed_type_needed} beds = {bed_count}"
        }

    else:
        # ── STALE DATA: Voice Call ──
        print(f"[Hospital Worker] {hospital_name}: data is STALE, triggering voice call")

        try:
            emergencies_ref().document(emergency_id).update({
                "routing_status": f"calling_{hospital_name.lower().replace(' ', '_')}"
            })
        except Exception:
            pass

        voice_result = await voice_agent.call(hospital, triage_result)

        verification_result = {
            "bed_available": voice_result.get("bed_available"),
            "method": "voice_call",
            "confidence": voice_result.get("confidence", "pending"),
            "raw_response": voice_result.get("raw_response", "")
        }

    # Store verification in Firestore
    try:
        hospital_verifications_ref().add({
            "emergency_id": emergency_id,
            "hospital_id": hospital_id,
            "method": verification_result["method"],
            "bed_available": verification_result["bed_available"],
            "confidence": verification_result["confidence"],
            "raw_response": verification_result.get("raw_response", ""),
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        print(f"[Hospital Worker] Failed to store verification: {e}")

    # Update routing status
    try:
        emergencies_ref().document(emergency_id).update({
            "routing_status": f"checked_{hospital_name.lower().replace(' ', '_')}"
        })
    except Exception:
        pass

    print(f"[Hospital Worker] {hospital_name}: bed_available={verification_result['bed_available']}, "
          f"method={verification_result['method']}")

    return {
        **hospital,
        "verification": verification_result
    }


async def check_parallel(hospitals: list, emergency: dict, emergency_id: str, triage_result: dict) -> list:
    """
    Check MULTIPLE hospitals simultaneously using asyncio.gather.
    Calls all hospitals at the same time — much faster than sequential.

    Args:
        hospitals: list of hospital dicts to check
        emergency: dict with emergency data
        emergency_id: Firestore document ID
        triage_result: parsed triage data

    Returns:
        list of hospital dicts with verification results
    """
    print(f"[Hospital Worker] Checking {len(hospitals)} hospitals IN PARALLEL...")

    tasks = [
        check(hospital, emergency, emergency_id, triage_result)
        for hospital in hospitals
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle any exceptions
    verified = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"[Hospital Worker] Error checking {hospitals[i].get('name')}: {result}")
            verified.append({
                **hospitals[i],
                "verification": {
                    "bed_available": None,
                    "method": "error",
                    "confidence": "low",
                    "raw_response": str(result)
                }
            })
        else:
            verified.append(result)

    available = [h for h in verified if h.get("verification", {}).get("bed_available")]
    print(f"[Hospital Worker] Parallel check complete: {len(available)}/{len(hospitals)} have beds")

    return verified
