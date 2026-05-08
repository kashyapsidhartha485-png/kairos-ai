"""
Kairos AI — Closer Agent
Finalizes hospital routing — updates DB, notifies driver & emergency contact.
PRD Section 7.4 (closing step)
"""
import os
from app.services.firebase_client import (
    emergencies_ref, ambulances_ref, emergency_events_ref, users_ref
)
from app.services.twilio_client import send_sms
from app.routers.driver import create_driver_notification
from datetime import datetime, timezone


async def close(winning_hospital: dict, emergency: dict, emergency_id: str):
    """
    Finalize hospital selection:
    1. Update emergency record with chosen hospital
    2. Update ambulance status to 'busy'
    3. Send navigation to driver via web dashboard notification
    4. Notify emergency contact via SMS
    5. Log event
    
    Args:
        winning_hospital: dict with id, name, lat, lng, reason, phone
        emergency: dict with emergency data
        emergency_id: Firestore document ID
    """
    hospital_id = winning_hospital.get("id")
    hospital_name = winning_hospital.get("name", "Hospital")
    hospital_lat = winning_hospital.get("lat", 0)
    hospital_lng = winning_hospital.get("lng", 0)
    reason = winning_hospital.get("reason", "Best available option")
    hospital_phone = winning_hospital.get("phone", "")

    # ① Update emergency record
    emergencies_ref().document(emergency_id).update({
        "chosen_hospital_id": hospital_id,
        "status": "routed",
        "routing_status": "routing_complete",
        "scoring_reason": reason
    })

    # ② Update ambulance status
    ambulance_id = emergency.get("ambulance_id")
    if ambulance_id:
        ambulances_ref().document(ambulance_id).update({
            "status": "busy"
        })

    # ③ Send navigation to driver via web dashboard notification
    if ambulance_id:
        hospital_nav_link = f"https://maps.google.com/?q={hospital_lat},{hospital_lng}"
        create_driver_notification(
            ambulance_id=ambulance_id,
            notification_type="hospital_confirmed",
            title="HOSPITAL CONFIRMED",
            message=(
                f"Hospital: {hospital_name}\n"
                f"Address: {winning_hospital.get('address', 'N/A')}\n"
                f"ER Phone: {hospital_phone}\n\n"
                f"Reason: {reason}\n\n"
                f"Proceed immediately."
            ),
            navigation_link=hospital_nav_link,
            metadata={
                "emergency_id": emergency_id,
                "hospital_id": hospital_id,
                "hospital_name": hospital_name,
                "hospital_lat": hospital_lat,
                "hospital_lng": hospital_lng
            }
        )

    # ④ Send SMS to emergency contact
    patient_id = emergency.get("patient_id")
    if patient_id:
        patient_doc = users_ref().document(patient_id).get()
        if patient_doc.exists:
            patient_data = patient_doc.to_dict()
            contact_phone = patient_data.get("emergency_contact_phone")
            patient_name = patient_data.get("name", "Your contact")
            if contact_phone:
                try:
                    sms_body = (
                        f"Update: {patient_name}'s ambulance is en route to "
                        f"{hospital_name}. ER Phone: {hospital_phone}"
                    )
                    send_sms(to=contact_phone, body=sms_body)
                except Exception as e:
                    print(f"[Closer Agent] SMS to emergency contact failed: {e}")

    # ⑤ Log event
    emergency_events_ref().add({
        "emergency_id": emergency_id,
        "event_type": "hospital_selected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "hospital_id": hospital_id,
            "hospital_name": hospital_name,
            "reason": reason
        }
    })

    print(f"[Closer Agent] Routing complete → {hospital_name} (reason: {reason})")
