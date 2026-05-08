"""
Kairos AI — Hospital Router
GET/POST /api/hospital/* — Hospital ER dashboard API.
PRD Section 6.3, 7.5
"""
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from app.services.firebase_client import (
    hospitals_ref, emergencies_ref, users_ref,
    patient_conditions_ref, ambulances_ref, emergency_events_ref
)
from app.services.twilio_client import send_sms
from app.services.maps_client import get_single_eta
from app.agents.orchestrator import rerun as orchestrator_rerun
from app.models.schemas import (
    HospitalStatusResponse, HospitalEmergencyView, PatientCard,
    ConfirmBedRequest, ConfirmBedResponse, AcknowledgeResponse,
    AmbulanceLocationResponse
)

router = APIRouter(prefix="/api/hospital", tags=["Hospital"])


# ──────────────────────────────────────────────
# GET /api/hospital/{id}/status
# ──────────────────────────────────────────────

@router.get("/{hospital_id}/status", response_model=HospitalStatusResponse)
async def get_hospital_status(hospital_id: str):
    """
    Return the current emergency routed to this hospital (if any).
    Includes patient card, triage result, ambulance ETA, and scoring reason.
    """
    hospital_doc = hospitals_ref().document(hospital_id).get()
    if not hospital_doc.exists:
        raise HTTPException(status_code=404, detail="Hospital not found")

    # Find active emergency routed to this hospital
    emergency = None
    emergency_id = None
    for doc in emergencies_ref().where("chosen_hospital_id", "==", hospital_id).stream():
        e = doc.to_dict()
        if e.get("status") in ["routed", "bed_confirmed"]:
            emergency = e
            emergency_id = doc.id
            break

    if not emergency:
        return HospitalStatusResponse(emergency=None, new_patient_alert=False)

    # Get patient card
    patient_card = None
    unidentified_notes = None
    patient_id = emergency.get("patient_id")
    if patient_id:
        patient_doc = users_ref().document(patient_id).get()
        if patient_doc.exists:
            p = patient_doc.to_dict()
            patient_card = PatientCard(
                name=p.get("name", ""),
                age=p.get("age", 0),
                blood_group=p.get("blood_group", ""),
                conditions=p.get("conditions"),
                allergies=p.get("allergies"),
                medications=p.get("medications"),
                emergency_contact_name=p.get("emergency_contact_name", ""),
                emergency_contact_phone=p.get("emergency_contact_phone", "")
            )
    else:
        unidentified_notes = emergency.get("bystander_notes")

    # Get triage result
    triage_result = None
    live_condition = None
    for doc in patient_conditions_ref().where("emergency_id", "==", emergency_id).limit(1).stream():
        cond = doc.to_dict()
        triage_result = cond.get("triage_result")
        live_condition = {
            "symptoms": cond.get("symptoms"),
            "vitals": cond.get("vitals"),
            "consciousness_level": cond.get("consciousness_level")
        }

    # Calculate ambulance ETA
    ambulance_eta = None
    ambulance_status = None
    ambulance_id = emergency.get("ambulance_id")
    if ambulance_id:
        amb_doc = ambulances_ref().document(ambulance_id).get()
        if amb_doc.exists:
            amb = amb_doc.to_dict()
            ambulance_status = amb.get("status")
            hospital_data = hospital_doc.to_dict()
            try:
                ambulance_eta = get_single_eta(
                    amb.get("current_lat"), amb.get("current_lng"),
                    hospital_data.get("lat"), hospital_data.get("lng")
                )
            except Exception:
                ambulance_eta = None

    # Check if alert is unacknowledged
    new_patient_alert = not emergency.get("alert_acknowledged", False)

    return HospitalStatusResponse(
        emergency=HospitalEmergencyView(
            id=emergency_id,
            patient=patient_card,
            unidentified_notes=unidentified_notes,
            triage_result=triage_result,
            live_condition=live_condition,
            ambulance_eta_minutes=ambulance_eta,
            ambulance_status=ambulance_status,
            scoring_reason=emergency.get("scoring_reason")
        ),
        new_patient_alert=new_patient_alert
    )


# ──────────────────────────────────────────────
# POST /api/hospital/{id}/confirm-bed
# ──────────────────────────────────────────────

@router.post("/{hospital_id}/confirm-bed", response_model=ConfirmBedResponse)
async def confirm_bed(hospital_id: str, request: ConfirmBedRequest):
    """
    Hospital confirms or denies bed availability.
    If unavailable, triggers re-routing to next best hospital.
    """
    emergency_doc = emergencies_ref().document(request.emergency_id).get()
    if not emergency_doc.exists:
        raise HTTPException(status_code=404, detail="Emergency not found")

    if request.status == "confirmed":
        emergencies_ref().document(request.emergency_id).update({
            "status": "bed_confirmed"
        })
        emergency_events_ref().add({
            "emergency_id": request.emergency_id,
            "event_type": "bed_confirmed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"hospital_id": hospital_id}
        })
        return ConfirmBedResponse(success=True, message="Bed confirmed.")

    elif request.status == "unavailable":
        emergency_events_ref().add({
            "emergency_id": request.emergency_id,
            "event_type": "bed_unavailable",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"hospital_id": hospital_id}
        })

        # Trigger re-routing in background
        asyncio.create_task(
            orchestrator_rerun(request.emergency_id, exclude_hospital_id=hospital_id)
        )

        return ConfirmBedResponse(
            success=True,
            re_routing=True,
            message="AI is re-routing ambulance to next available hospital."
        )

    raise HTTPException(status_code=400, detail="Status must be 'confirmed' or 'unavailable'")


# ──────────────────────────────────────────────
# POST /api/hospital/{id}/acknowledge
# ──────────────────────────────────────────────

@router.post("/{hospital_id}/acknowledge", response_model=AcknowledgeResponse)
async def acknowledge_alert(hospital_id: str):
    """Mark the incoming patient alert as acknowledged by the hospital."""
    # Find the active emergency for this hospital
    for doc in emergencies_ref().where("chosen_hospital_id", "==", hospital_id).stream():
        e = doc.to_dict()
        if e.get("status") in ["routed", "bed_confirmed"]:
            emergencies_ref().document(doc.id).update({
                "alert_acknowledged": True
            })
            return AcknowledgeResponse(success=True)

    raise HTTPException(status_code=404, detail="No active emergency for this hospital")


# ──────────────────────────────────────────────
# GET /api/hospital/{id}/ambulance-location
# ──────────────────────────────────────────────

@router.get("/{hospital_id}/ambulance-location", response_model=AmbulanceLocationResponse)
async def get_hospital_ambulance_location(hospital_id: str):
    """Return ambulance location and ETA to hospital."""
    hospital_doc = hospitals_ref().document(hospital_id).get()
    if not hospital_doc.exists:
        raise HTTPException(status_code=404, detail="Hospital not found")

    hospital = hospital_doc.to_dict()

    # Find active emergency
    for doc in emergencies_ref().where("chosen_hospital_id", "==", hospital_id).stream():
        e = doc.to_dict()
        if e.get("status") in ["routed", "bed_confirmed"]:
            ambulance_id = e.get("ambulance_id")
            if ambulance_id:
                amb_doc = ambulances_ref().document(ambulance_id).get()
                if amb_doc.exists:
                    amb = amb_doc.to_dict()
                    try:
                        eta = get_single_eta(
                            amb.get("current_lat"), amb.get("current_lng"),
                            hospital.get("lat"), hospital.get("lng")
                        )
                    except Exception:
                        eta = -1.0

                    return AmbulanceLocationResponse(
                        lat=amb.get("current_lat", 0),
                        lng=amb.get("current_lng", 0),
                        eta_minutes=eta
                    )

    raise HTTPException(status_code=404, detail="No ambulance en route to this hospital")


async def start_acknowledge_timer(emergency_id: str, hospital_id: str):
    """
    Background task: if hospital doesn't acknowledge within 2 minutes,
    send SMS to hospital phone as fallback.
    """
    await asyncio.sleep(120)  # 2 minutes (set to 10 for testing)

    # Check if acknowledged
    emergency_doc = emergencies_ref().document(emergency_id).get()
    if not emergency_doc.exists:
        return

    emergency = emergency_doc.to_dict()
    if emergency.get("alert_acknowledged"):
        return

    # Not acknowledged — send SMS to hospital
    hospital_doc = hospitals_ref().document(hospital_id).get()
    if hospital_doc.exists:
        hospital = hospital_doc.to_dict()
        phone = hospital.get("phone")
        if phone:
            try:
                send_sms(
                    to=phone,
                    body=(
                        f"URGENT: Kairos AI emergency patient incoming. "
                        f"Emergency ID: {emergency_id}. "
                        f"Please prepare ER immediately. Alert not acknowledged on dashboard."
                    )
                )
                print(f"[Hospital Timer] Sent unacknowledged alert SMS to {hospital.get('name')}")
            except Exception as e:
                print(f"[Hospital Timer] SMS failed: {e}")
