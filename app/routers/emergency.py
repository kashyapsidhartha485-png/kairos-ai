"""
Kairos AI — Emergency Router
Handles emergency identification, condition input, routing status, and manual info.
PRD Sections 6.1, 7.2, 7.4, 9.4, 9.5, 10.1
"""
import os
import math
import uuid
import time
import asyncio
import tempfile
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from typing import Optional

from app.agents import face_agent, first_aid_agent, triage_agent
from app.agents.orchestrator import run as orchestrator_run
from app.services.firebase_client import (
    emergencies_ref, users_ref, patient_conditions_ref,
    emergency_events_ref, hospitals_ref, ambulances_ref
)
from app.services.maps_client import get_distance_matrix
from app.services.twilio_client import send_sms
from app.agents.prep_agent import generate as generate_prep
from app.routers.driver import create_driver_notification
from app.models.schemas import (
    IdentifyResponse, PatientCard, FirstAidGuidance,
    DuplicateCheckResponse, ManualInfoRequest, ManualInfoResponse,
    ConditionRequest, ConditionResponse, RoutingStatusResponse,
    HospitalCheckStatus, DispatchResponse, AmbulanceInfo,
    AmbulanceLocationResponse
)

router = APIRouter(prefix="/api/emergency", tags=["Emergency"])


# ──────────────────────────────────────────────
# POST /api/emergency/identify
# ──────────────────────────────────────────────

@router.post("/identify", response_model=IdentifyResponse)
async def identify_patient(
    photo: UploadFile = File(...),
    lat: float = Form(...),
    lng: float = Form(...)
):
    """
    Identify a patient from a bystander-submitted photo.
    Creates emergency record, runs face matching, generates first-aid guidance.
    """
    start_time = time.time()

    # ── Duplicate check: nearby active emergencies within 100m in last 5 min ──
    recent_emergencies = emergencies_ref().where("status", "==", "active").stream()
    for doc in recent_emergencies:
        e = doc.to_dict()
        e_lat = e.get("bystander_lat", 0)
        e_lng = e.get("bystander_lng", 0)
        e_created = e.get("created_at", "")

        # Check distance (approx 0.001 deg ≈ 100m)
        dist = math.sqrt((e_lat - lat) ** 2 + (e_lng - lng) ** 2)
        if dist < 0.001:
            # Check time (within 5 minutes)
            try:
                if isinstance(e_created, str):
                    created_dt = datetime.fromisoformat(e_created.replace("Z", "+00:00"))
                else:
                    created_dt = e_created
                if datetime.now(timezone.utc) - created_dt < timedelta(minutes=5):
                    return IdentifyResponse(
                        emergency_id=doc.id,
                        identification_status="duplicate",
                        warning="Duplicate emergency detected at this location."
                    )
            except (ValueError, TypeError):
                pass

    # ── Create emergency record ──
    emergency_id = str(uuid.uuid4())
    emergencies_ref().document(emergency_id).set({
        "patient_id": None,
        "bystander_lat": lat,
        "bystander_lng": lng,
        "bystander_notes": None,
        "status": "active",
        "ambulance_id": None,
        "chosen_hospital_id": None,
        "identification_status": None,
        "routing_status": None,
        "alert_acknowledged": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # ── Save photo temporarily for face matching ──
    suffix = os.path.splitext(photo.filename or "photo.jpg")[1] or ".jpg"
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_file.write(await photo.read())
    tmp_file.close()

    try:
        # ── Run face matching ──
        match_result = await face_agent.match(tmp_file.name)
    except ValueError as e:
        # Face not detected
        os.unlink(tmp_file.name)
        emergencies_ref().document(emergency_id).update({
            "identification_status": "not_identified"
        })
        return IdentifyResponse(
            emergency_id=emergency_id,
            identification_status="not_identified",
            warning="Face could not be detected in the uploaded photo."
        )
    finally:
        # Always clean up temp file
        try:
            os.unlink(tmp_file.name)
        except OSError:
            pass

    elapsed_ms = int((time.time() - start_time) * 1000)

    # ── Process match result ──
    identification_status = match_result["identification_status"]
    confidence = match_result.get("confidence")
    patient_card = None
    first_aid = None
    warning = match_result.get("warning")

    if identification_status == "identified":
        patient_data = match_result["patient_data"]
        patient_id = match_result["patient_id"]

        # ── Check if this patient already has a recent active emergency ──
        existing_emergencies = emergencies_ref().where("patient_id", "==", patient_id).where("status", "==", "active").stream()
        for existing_doc in existing_emergencies:
            existing = existing_doc.to_dict()
            e_created = existing.get("created_at", "")
            try:
                if isinstance(e_created, str):
                    created_dt = datetime.fromisoformat(e_created.replace("Z", "+00:00"))
                else:
                    created_dt = e_created
                if datetime.now(timezone.utc) - created_dt < timedelta(minutes=10):
                    # Same person already has an active emergency — delete the new one
                    emergencies_ref().document(emergency_id).delete()
                    return IdentifyResponse(
                        emergency_id=existing_doc.id,
                        identification_status="already_reported",
                        warning=f"This patient ({patient_data.get('name', 'Unknown')}) already has an active emergency.",
                        patient_card=PatientCard(
                            name=patient_data.get("name", ""),
                            age=patient_data.get("age", 0),
                            blood_group=patient_data.get("blood_group", ""),
                            conditions=patient_data.get("conditions"),
                            allergies=patient_data.get("allergies"),
                            medications=patient_data.get("medications"),
                            emergency_contact_name=patient_data.get("emergency_contact_name", ""),
                            emergency_contact_phone=patient_data.get("emergency_contact_phone", "")
                        )
                    )
            except (ValueError, TypeError):
                pass

        # Update emergency with patient
        emergencies_ref().document(emergency_id).update({
            "patient_id": patient_id,
            "identification_status": "identified"
        })

        # Build patient card
        patient_card = PatientCard(
            name=patient_data.get("name", ""),
            age=patient_data.get("age", 0),
            blood_group=patient_data.get("blood_group", ""),
            conditions=patient_data.get("conditions"),
            allergies=patient_data.get("allergies"),
            medications=patient_data.get("medications"),
            emergency_contact_name=patient_data.get("emergency_contact_name", ""),
            emergency_contact_phone=patient_data.get("emergency_contact_phone", "")
        )

        # Generate first-aid guidance
        first_aid_result = await first_aid_agent.generate(patient_data)
        first_aid = FirstAidGuidance(**first_aid_result)

    else:
        emergencies_ref().document(emergency_id).update({
            "identification_status": "not_identified"
        })

    # ── Log event ──
    emergency_events_ref().add({
        "emergency_id": emergency_id,
        "event_type": "identification_complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "identification_status": identification_status,
            "confidence": confidence,
            "time_taken_ms": elapsed_ms,
            "distance": match_result.get("distance")
        }
    })

    return IdentifyResponse(
        emergency_id=emergency_id,
        identification_status=identification_status,
        confidence=confidence,
        patient=patient_card,
        first_aid_guidance=first_aid,
        warning=warning
    )


# ──────────────────────────────────────────────
# GET /api/emergency/nearby
# ──────────────────────────────────────────────

@router.get("/nearby", response_model=DuplicateCheckResponse)
async def check_nearby(lat: float, lng: float):
    """Check for duplicate emergencies near the given coordinates."""
    recent_emergencies = emergencies_ref().where("status", "==", "active").stream()

    for doc in recent_emergencies:
        e = doc.to_dict()
        e_lat = e.get("bystander_lat", 0)
        e_lng = e.get("bystander_lng", 0)
        e_created = e.get("created_at", "")

        dist = math.sqrt((e_lat - lat) ** 2 + (e_lng - lng) ** 2)
        if dist < 0.001:
            try:
                if isinstance(e_created, str):
                    created_dt = datetime.fromisoformat(e_created.replace("Z", "+00:00"))
                else:
                    created_dt = e_created
                if datetime.now(timezone.utc) - created_dt < timedelta(minutes=5):
                    return DuplicateCheckResponse(
                        duplicate=True,
                        existing_emergency_id=doc.id
                    )
            except (ValueError, TypeError):
                pass

    return DuplicateCheckResponse(duplicate=False)


# ──────────────────────────────────────────────
# POST /api/emergency/{id}/manual
# ──────────────────────────────────────────────

@router.post("/{emergency_id}/manual", response_model=ManualInfoResponse)
async def submit_manual_info(
    emergency_id: str,
    approximate_age: Optional[int] = Form(None),
    gender: Optional[str] = Form(None),
    visible_injuries: Optional[str] = Form(None),
    known_conditions: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None)
):
    """Submit manual patient information when face recognition fails."""
    emergency_doc = emergencies_ref().document(emergency_id).get()
    if not emergency_doc.exists:
        raise HTTPException(status_code=404, detail="Emergency not found")

    notes = f"Age: {approximate_age}, Gender: {gender}, " \
            f"Injuries: {visible_injuries}, Conditions: {known_conditions}"

    update_data = {"bystander_notes": notes}

    # Handle optional document photo (NOT a face recognition photo)
    if photo:
        # For now, store as base64 or note that a photo was attached
        update_data["has_document_photo"] = True

    emergencies_ref().document(emergency_id).update(update_data)

    return ManualInfoResponse(success=True)


# ──────────────────────────────────────────────
# POST /api/emergency/{id}/dispatch
# ──────────────────────────────────────────────

@router.post("/{emergency_id}/dispatch", response_model=DispatchResponse)
async def dispatch_ambulance(emergency_id: str):
    """
    Assign the best available ambulance based on real drive time.
    PRD Sections 7.3, 8.1, 8.2, 8.3
    """
    # Fetch emergency
    emergency_doc = emergencies_ref().document(emergency_id).get()
    if not emergency_doc.exists:
        raise HTTPException(status_code=404, detail="Emergency not found")
    emergency = emergency_doc.to_dict()

    bystander_lat = emergency.get("bystander_lat")
    bystander_lng = emergency.get("bystander_lng")

    # Fetch patient data for capability filtering
    patient_data = None
    patient_id = emergency.get("patient_id")
    if patient_id:
        patient_doc = users_ref().document(patient_id).get()
        if patient_doc.exists:
            patient_data = patient_doc.to_dict()

    # Fetch available ambulances
    available_ambulances = []
    for doc in ambulances_ref().where("status", "==", "available").stream():
        amb = doc.to_dict()
        amb["id"] = doc.id
        available_ambulances.append(amb)

    if not available_ambulances:
        raise HTTPException(status_code=503, detail="No ambulances available")

    # Capability filter: if patient has cardiac/neurological/trauma conditions,
    # filter out BLS ambulances (keep only ALS)
    if patient_data:
        conditions = (patient_data.get("conditions") or "").lower()
        needs_als = any(
            kw in conditions
            for kw in ["cardiac", "heart", "neurological", "neuro", "trauma", "stroke"]
        )
        if needs_als:
            als_ambulances = [a for a in available_ambulances if a.get("capability") == "ALS"]
            if als_ambulances:
                available_ambulances = als_ambulances

    # Get drive times from Distance Matrix API
    destination = f"{bystander_lat},{bystander_lng}"
    origins = [
        f"{a['current_lat']},{a['current_lng']}" for a in available_ambulances
    ]

    try:
        drive_times = get_distance_matrix(origins=origins, destination=destination)
    except Exception as e:
        print(f"[Dispatch] Distance Matrix error: {e}")
        # Fallback: use straight-line distance
        drive_times = {}
        for i, amb in enumerate(available_ambulances):
            dist = math.sqrt(
                (amb["current_lat"] - bystander_lat) ** 2 +
                (amb["current_lng"] - bystander_lng) ** 2
            )
            drive_times[i] = {"duration_seconds": int(dist * 100000)}

    # Rank by lowest drive time
    ranked = []
    for i, amb in enumerate(available_ambulances):
        dt = drive_times.get(i)
        if dt:
            amb["drive_time_seconds"] = dt["duration_seconds"]
            ranked.append(amb)

    ranked.sort(key=lambda a: a.get("drive_time_seconds", 999999))

    if not ranked:
        raise HTTPException(status_code=503, detail="Could not determine ambulance drive times")

    winner = ranked[0]
    eta_minutes = round(winner["drive_time_seconds"] / 60, 1)

    # Update ambulance status
    ambulances_ref().document(winner["id"]).update({"status": "dispatched"})

    # Update emergency
    emergencies_ref().document(emergency_id).update({"ambulance_id": winner["id"]})

    # Generate prep instructions
    prep_instructions = []
    if patient_data:
        prep_instructions = await generate_prep(patient_data, emergency)
    else:
        prep_instructions = ["Prepare standard emergency kit", "Ready the stretcher"]

    # Store prep instructions on emergency for driver dashboard
    emergencies_ref().document(emergency_id).update({
        "prep_instructions": prep_instructions
    })

    # Send driver notification (web dashboard)
    patient_name = patient_data.get("name", "Unidentified") if patient_data else "Unidentified"
    blood_group = patient_data.get("blood_group", "Unknown") if patient_data else "Unknown"
    conditions_str = patient_data.get("conditions", "None") if patient_data else "None"
    prep_text = "\n".join([f"  - {p}" for p in prep_instructions])
    pickup_link = f"https://maps.google.com/?q={bystander_lat},{bystander_lng}"

    create_driver_notification(
        ambulance_id=winner["id"],
        notification_type="dispatch",
        title="EMERGENCY DISPATCH",
        message=(
            f"Patient: {patient_name}\n"
            f"Blood Group: {blood_group}\n"
            f"Conditions: {conditions_str}\n\n"
            f"Prep Instructions:\n{prep_text}"
        ),
        navigation_link=pickup_link,
        metadata={
            "emergency_id": emergency_id,
            "patient_name": patient_name,
            "pickup_lat": bystander_lat,
            "pickup_lng": bystander_lng
        }
    )

    # Send SMS to emergency contact
    if patient_data:
        contact_phone = patient_data.get("emergency_contact_phone")
        if contact_phone:
            maps_link = f"https://maps.google.com/?q={bystander_lat},{bystander_lng}"
            try:
                send_sms(
                    to=contact_phone,
                    body=(
                        f"Emergency alert: {patient_data.get('name')} has been in an emergency. "
                        f"An ambulance has been dispatched. Location: {maps_link}"
                    )
                )
            except Exception as e:
                print(f"[Dispatch] SMS to emergency contact failed: {e}")

    # Log event
    emergency_events_ref().add({
        "emergency_id": emergency_id,
        "event_type": "ambulance_dispatched",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "ambulance_id": winner["id"],
            "driver_name": winner.get("driver_name"),
            "eta_minutes": eta_minutes
        }
    })

    return DispatchResponse(
        assigned_ambulance=AmbulanceInfo(
            id=winner["id"],
            driver_name=winner.get("driver_name", "Unknown"),
            current_lat=winner.get("current_lat", 0),
            current_lng=winner.get("current_lng", 0),
            eta_minutes=eta_minutes
        ),
        prep_instructions=prep_instructions
    )


# ──────────────────────────────────────────────
# POST /api/emergency/{id}/condition
# ──────────────────────────────────────────────

@router.post("/{emergency_id}/condition", response_model=ConditionResponse)
async def submit_condition(
    emergency_id: str,
    condition: ConditionRequest
):
    """
    Companion submits patient condition. Triggers triage + hospital routing in parallel.
    """
    emergency_doc = emergencies_ref().document(emergency_id).get()
    if not emergency_doc.exists:
        raise HTTPException(status_code=404, detail="Emergency not found")

    # Insert patient condition
    condition_id = str(uuid.uuid4())
    condition_text = (
        f"Symptoms: {condition.symptoms}. "
        f"Vitals: {condition.vitals or 'not reported'}. "
        f"Consciousness: {condition.consciousness_level or 'not reported'}. "
        f"Visible injuries: {condition.visible_injuries or 'none reported'}."
    )

    patient_conditions_ref().document(condition_id).set({
        "emergency_id": emergency_id,
        "symptoms": condition.symptoms,
        "vitals": condition.vitals,
        "consciousness_level": condition.consciousness_level,
        "triage_result": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # Trigger triage FIRST, then orchestrator (triage result feeds into routing)
    async def run_agents():
        try:
            # Step 1: Triage agent analyzes symptoms + checks patient history
            await triage_agent.extract(condition_text, condition_id, emergency_id)
            # Step 2: Orchestrator agent routes to best hospital (uses triage result)
            await orchestrator_run(emergency_id)
        except Exception as e:
            print(f"[Background] Agent pipeline error: {e}")
            import traceback
            traceback.print_exc()

    asyncio.create_task(run_agents())

    return ConditionResponse(
        success=True,
        message="Condition received. AI routing in progress."
    )


# ──────────────────────────────────────────────
# GET /api/emergency/{id}/routing-status
# ──────────────────────────────────────────────

@router.get("/{emergency_id}/routing-status", response_model=RoutingStatusResponse)
async def get_routing_status(emergency_id: str):
    """Return real-time routing state for frontend polling."""
    emergency_doc = emergencies_ref().document(emergency_id).get()
    if not emergency_doc.exists:
        raise HTTPException(status_code=404, detail="Emergency not found")

    emergency = emergency_doc.to_dict()
    routing_status = emergency.get("routing_status", "pending")

    # Fetch hospital verifications for this emergency
    hospitals_checked = []
    verifications = hospital_verifications_ref = []
    from app.services.firebase_client import hospital_verifications_ref as hv_ref
    for doc in hv_ref().where("emergency_id", "==", emergency_id).stream():
        v = doc.to_dict()
        # Get hospital name
        h_id = v.get("hospital_id")
        h_name = h_id  # fallback
        if h_id:
            h_doc = hospitals_ref().document(h_id).get()
            if h_doc.exists:
                h_name = h_doc.to_dict().get("name", h_id)

        hospitals_checked.append(HospitalCheckStatus(
            name=h_name,
            status="available" if v.get("bed_available") else "unavailable",
            method=v.get("method")
        ))

    # Chosen hospital
    chosen = None
    if emergency.get("chosen_hospital_id"):
        h_doc = hospitals_ref().document(emergency["chosen_hospital_id"]).get()
        if h_doc.exists:
            h_data = h_doc.to_dict()
            chosen = {
                "id": emergency["chosen_hospital_id"],
                "name": h_data.get("name"),
                "reason": emergency.get("scoring_reason"),
                "distance_km": None
            }

    return RoutingStatusResponse(
        routing_status=routing_status,
        hospitals_checked=hospitals_checked,
        chosen_hospital=chosen
    )


# ──────────────────────────────────────────────
# GET /api/emergency/{id}/ambulance-location
# ──────────────────────────────────────────────

@router.get("/{emergency_id}/ambulance-location", response_model=AmbulanceLocationResponse)
async def get_ambulance_location(emergency_id: str):
    """Return current ambulance location and recalculated ETA."""
    emergency_doc = emergencies_ref().document(emergency_id).get()
    if not emergency_doc.exists:
        raise HTTPException(status_code=404, detail="Emergency not found")

    emergency = emergency_doc.to_dict()
    ambulance_id = emergency.get("ambulance_id")
    if not ambulance_id:
        raise HTTPException(status_code=404, detail="No ambulance assigned")

    amb_doc = ambulances_ref().document(ambulance_id).get()
    if not amb_doc.exists:
        raise HTTPException(status_code=404, detail="Ambulance not found")

    amb = amb_doc.to_dict()

    # Determine destination (hospital if routed, otherwise bystander location)
    dest_lat = emergency.get("bystander_lat")
    dest_lng = emergency.get("bystander_lng")

    if emergency.get("chosen_hospital_id"):
        h_doc = hospitals_ref().document(emergency["chosen_hospital_id"]).get()
        if h_doc.exists:
            h_data = h_doc.to_dict()
            dest_lat = h_data.get("lat", dest_lat)
            dest_lng = h_data.get("lng", dest_lng)

    # Recalculate ETA
    try:
        from app.services.maps_client import get_single_eta
        eta = get_single_eta(
            amb.get("current_lat"), amb.get("current_lng"),
            dest_lat, dest_lng
        )
    except Exception:
        eta = -1.0

    return AmbulanceLocationResponse(
        lat=amb.get("current_lat", 0),
        lng=amb.get("current_lng", 0),
        eta_minutes=eta
    )
