"""
Kairos AI — Driver Router
Full web dashboard API for ambulance drivers.
Replaces Telegram — driver polls this API for real-time updates.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.services.firebase_client import (
    ambulances_ref, emergencies_ref, users_ref, hospitals_ref,
    driver_notifications_ref
)
from app.models.schemas import DriverStatusResponse, PatientCard

router = APIRouter(prefix="/api/driver", tags=["Driver"])


# ──────────────────────────────────────────────
# Response Models
# ──────────────────────────────────────────────

class DriverNotification(BaseModel):
    id: str
    type: str  # "dispatch" | "hospital_confirmed" | "reroute" | "info"
    title: str
    message: str
    navigation_link: Optional[str] = None
    timestamp: str
    read: bool = False
    metadata: Optional[dict] = None


class DriverNotificationsResponse(BaseModel):
    notifications: List[DriverNotification]
    unread_count: int


class DriverDashboardResponse(BaseModel):
    """Full dashboard state for the driver."""
    ambulance_id: str
    driver_name: str
    status: str  # available | dispatched | busy

    # Active emergency (if dispatched/busy)
    emergency_id: Optional[str] = None
    patient: Optional[PatientCard] = None
    unidentified_notes: Optional[str] = None

    # Pickup — accident location + directions
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    pickup_nav_link: Optional[str] = None          # Google Maps pin
    pickup_directions_link: Optional[str] = None   # Google Maps turn-by-turn directions

    # Ambulance current position
    ambulance_lat: Optional[float] = None
    ambulance_lng: Optional[float] = None

    # Prep instructions
    prep_instructions: Optional[List[str]] = None

    # Hospital (once routing completes)
    hospital_name: Optional[str] = None
    hospital_address: Optional[str] = None
    hospital_phone: Optional[str] = None
    hospital_lat: Optional[float] = None
    hospital_lng: Optional[float] = None
    hospital_nav_link: Optional[str] = None        # Google Maps pin
    hospital_directions_link: Optional[str] = None # Google Maps turn-by-turn directions
    scoring_reason: Optional[str] = None

    # Notifications
    unread_notifications: int = 0


class DriverLoginRequest(BaseModel):
    ambulance_id: str
    driver_phone: str


class DriverLoginResponse(BaseModel):
    success: bool
    ambulance_id: Optional[str] = None
    driver_name: Optional[str] = None
    message: str


# ──────────────────────────────────────────────
# POST /api/driver/login
# ──────────────────────────────────────────────

@router.post("/login", response_model=DriverLoginResponse)
async def driver_login(request: DriverLoginRequest):
    """
    Simple driver authentication via ambulance ID + phone number.
    No complex auth — just verify the ambulance exists and phone matches.
    """
    amb_doc = ambulances_ref().document(request.ambulance_id).get()
    if not amb_doc.exists:
        return DriverLoginResponse(
            success=False,
            message="Ambulance ID not found"
        )

    amb = amb_doc.to_dict()
    if amb.get("driver_phone") != request.driver_phone:
        return DriverLoginResponse(
            success=False,
            message="Phone number doesn't match"
        )

    return DriverLoginResponse(
        success=True,
        ambulance_id=request.ambulance_id,
        driver_name=amb.get("driver_name", "Driver"),
        message="Login successful"
    )


# ──────────────────────────────────────────────
# GET /api/driver/{ambulance_id}/dashboard
# ──────────────────────────────────────────────

@router.get("/{ambulance_id}/dashboard", response_model=DriverDashboardResponse)
async def get_driver_dashboard(ambulance_id: str):
    """
    Returns the FULL dashboard state for a driver.
    The frontend polls this every few seconds for real-time updates.
    """
    amb_doc = ambulances_ref().document(ambulance_id).get()
    if not amb_doc.exists:
        raise HTTPException(status_code=404, detail="Ambulance not found")

    amb = amb_doc.to_dict()
    status = amb.get("status", "available")
    amb_lat = amb.get("current_lat")
    amb_lng = amb.get("current_lng")

    # Base response (no active emergency)
    response = DriverDashboardResponse(
        ambulance_id=ambulance_id,
        driver_name=amb.get("driver_name", "Driver"),
        status=status,
        ambulance_lat=amb_lat,
        ambulance_lng=amb_lng
    )

    if status == "available":
        # Count unread notifications (single-field query + Python filter to avoid composite index)
        all_notifs = driver_notifications_ref() \
            .where("ambulance_id", "==", ambulance_id) \
            .stream()
        response.unread_notifications = sum(1 for n in all_notifs if not n.to_dict().get("read", False))
        return response

    # Find the active emergency for this ambulance
    emergency = None
    emergency_id = None
    for doc in emergencies_ref().where("ambulance_id", "==", ambulance_id).stream():
        e = doc.to_dict()
        if e.get("status") in ["active", "routed", "bed_confirmed"]:
            emergency = e
            emergency_id = doc.id
            break

    if not emergency:
        response.unread_notifications = 0
        return response

    response.emergency_id = emergency_id

    # Pickup location — accident site with DIRECTIONS
    pickup_lat = emergency.get("bystander_lat")
    pickup_lng = emergency.get("bystander_lng")
    response.pickup_lat = pickup_lat
    response.pickup_lng = pickup_lng
    if pickup_lat and pickup_lng:
        # Simple location pin
        response.pickup_nav_link = f"https://maps.google.com/?q={pickup_lat},{pickup_lng}"
        # Turn-by-turn directions from ambulance current location
        if amb_lat and amb_lng:
            response.pickup_directions_link = (
                f"https://www.google.com/maps/dir/?api=1"
                f"&origin={amb_lat},{amb_lng}"
                f"&destination={pickup_lat},{pickup_lng}"
                f"&travelmode=driving"
            )
        else:
            # If no ambulance position yet, directions from 'current location'
            response.pickup_directions_link = (
                f"https://www.google.com/maps/dir/?api=1"
                f"&destination={pickup_lat},{pickup_lng}"
                f"&travelmode=driving"
            )

    # Patient info
    patient_id = emergency.get("patient_id")
    if patient_id:
        patient_doc = users_ref().document(patient_id).get()
        if patient_doc.exists:
            p = patient_doc.to_dict()
            response.patient = PatientCard(
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
        response.unidentified_notes = emergency.get("bystander_notes")

    # Prep instructions (stored on emergency when dispatched)
    response.prep_instructions = emergency.get("prep_instructions")

    # Hospital info (if routing is complete)
    hospital_id = emergency.get("chosen_hospital_id")
    if hospital_id:
        h_doc = hospitals_ref().document(hospital_id).get()
        if h_doc.exists:
            h = h_doc.to_dict()
            response.hospital_name = h.get("name")
            response.hospital_address = h.get("address")
            response.hospital_phone = h.get("phone")
            response.hospital_lat = h.get("lat")
            response.hospital_lng = h.get("lng")
            if h.get("lat") and h.get("lng"):
                response.hospital_nav_link = f"https://maps.google.com/?q={h['lat']},{h['lng']}"
                # Turn-by-turn directions from ambulance/pickup to hospital
                origin_lat = amb_lat or pickup_lat
                origin_lng = amb_lng or pickup_lng
                if origin_lat and origin_lng:
                    response.hospital_directions_link = (
                        f"https://www.google.com/maps/dir/?api=1"
                        f"&origin={origin_lat},{origin_lng}"
                        f"&destination={h['lat']},{h['lng']}"
                        f"&travelmode=driving"
                    )
            response.scoring_reason = emergency.get("scoring_reason")

    # Unread notifications (single-field query + Python filter to avoid composite index)
    all_notifs = driver_notifications_ref() \
        .where("ambulance_id", "==", ambulance_id) \
        .stream()
    response.unread_notifications = sum(1 for n in all_notifs if not n.to_dict().get("read", False))

    return response


# ──────────────────────────────────────────────
# GET /api/driver/{ambulance_id}/notifications
# ──────────────────────────────────────────────

@router.get("/{ambulance_id}/notifications", response_model=DriverNotificationsResponse)
async def get_driver_notifications(ambulance_id: str):
    """
    Get all notifications for a driver (dispatch alerts, hospital nav, etc.).
    This replaces Telegram messages — the driver dashboard shows these as alerts.
    """
    notifications = []
    unread_count = 0

    docs = driver_notifications_ref() \
        .where("ambulance_id", "==", ambulance_id) \
        .limit(50) \
        .stream()

    for doc in docs:
        n = doc.to_dict()
        is_read = n.get("read", False)
        if not is_read:
            unread_count += 1

        notifications.append(DriverNotification(
            id=doc.id,
            type=n.get("type", "info"),
            title=n.get("title", ""),
            message=n.get("message", ""),
            navigation_link=n.get("navigation_link"),
            timestamp=n.get("timestamp", ""),
            read=is_read,
            metadata=n.get("metadata")
        ))

    # Sort by timestamp descending (avoids needing Firestore composite index)
    notifications.sort(key=lambda n: n.timestamp, reverse=True)

    return DriverNotificationsResponse(
        notifications=notifications,
        unread_count=unread_count
    )


# ──────────────────────────────────────────────
# POST /api/driver/{ambulance_id}/notifications/{id}/read
# ──────────────────────────────────────────────

@router.post("/{ambulance_id}/notifications/{notification_id}/read")
async def mark_notification_read(ambulance_id: str, notification_id: str):
    """Mark a notification as read."""
    doc = driver_notifications_ref().document(notification_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Notification not found")

    driver_notifications_ref().document(notification_id).update({"read": True})
    return {"success": True}


# ──────────────────────────────────────────────
# POST /api/driver/{ambulance_id}/complete
# ──────────────────────────────────────────────

@router.post("/{ambulance_id}/complete")
async def complete_emergency(ambulance_id: str):
    """
    Driver marks the emergency as complete (patient delivered to hospital).
    Resets ambulance status to 'available'.
    """
    amb_doc = ambulances_ref().document(ambulance_id).get()
    if not amb_doc.exists:
        raise HTTPException(status_code=404, detail="Ambulance not found")

    # Find and close the active emergency
    for doc in emergencies_ref().where("ambulance_id", "==", ambulance_id).stream():
        e = doc.to_dict()
        if e.get("status") in ["active", "routed", "bed_confirmed"]:
            emergencies_ref().document(doc.id).update({
                "status": "completed"
            })
            break

    # Reset ambulance to available
    ambulances_ref().document(ambulance_id).update({
        "status": "available"
    })

    return {"success": True, "message": "Emergency completed. Ambulance is now available."}


# ──────────────────────────────────────────────
# GET /api/driver/{ambulance_id}/status (legacy)
# ──────────────────────────────────────────────

@router.get("/{ambulance_id}/status", response_model=DriverStatusResponse)
async def get_driver_status(ambulance_id: str):
    """
    Legacy status endpoint. Use /dashboard for the full driver view.
    """
    amb_doc = ambulances_ref().document(ambulance_id).get()
    if not amb_doc.exists:
        raise HTTPException(status_code=404, detail="Ambulance not found")

    amb = amb_doc.to_dict()
    status = amb.get("status", "available")

    if status == "available":
        return DriverStatusResponse(status="available")

    # Find the emergency
    emergency = None
    emergency_id = None
    for doc in emergencies_ref().where("ambulance_id", "==", ambulance_id).stream():
        e = doc.to_dict()
        if e.get("status") in ["active", "routed", "bed_confirmed"]:
            emergency = e
            emergency_id = doc.id
            break

    if not emergency:
        return DriverStatusResponse(status=status)

    patient_card = None
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

    chosen_hospital = None
    hospital_id = emergency.get("chosen_hospital_id")
    if hospital_id:
        h_doc = hospitals_ref().document(hospital_id).get()
        if h_doc.exists:
            h = h_doc.to_dict()
            chosen_hospital = {
                "id": hospital_id,
                "name": h.get("name"),
                "lat": h.get("lat"),
                "lng": h.get("lng"),
                "address": h.get("address"),
                "phone": h.get("phone")
            }

    return DriverStatusResponse(
        status=status,
        emergency_id=emergency_id,
        patient=patient_card,
        prep_instructions=emergency.get("prep_instructions"),
        pickup_lat=emergency.get("bystander_lat"),
        pickup_lng=emergency.get("bystander_lng"),
        routing_status=emergency.get("routing_status"),
        chosen_hospital=chosen_hospital
    )


# ──────────────────────────────────────────────
# Helper: Create a driver notification
# (called from dispatch, closer_agent, etc.)
# ──────────────────────────────────────────────

def create_driver_notification(
    ambulance_id: str,
    notification_type: str,
    title: str,
    message: str,
    navigation_link: str = None,
    metadata: dict = None
):
    """
    Store a notification for the driver in Firebase.
    The driver dashboard polls for these and shows them as alerts.
    
    This replaces Telegram messages entirely.
    """
    notif_id = str(uuid.uuid4())
    driver_notifications_ref().document(notif_id).set({
        "ambulance_id": ambulance_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "navigation_link": navigation_link,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "read": False,
        "metadata": metadata or {}
    })
    print(f"[Driver Notification] {notification_type}: {title} → ambulance {ambulance_id}")
    return notif_id
