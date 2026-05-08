"""
Kairos AI — Ambulance Router
POST /api/ambulance/location-update — Real-time ambulance location pings.
"""
from fastapi import APIRouter, HTTPException
from app.services.firebase_client import ambulances_ref
from app.models.schemas import LocationUpdateRequest, LocationUpdateResponse

router = APIRouter(prefix="/api/ambulance", tags=["Ambulance"])


@router.post("/location-update", response_model=LocationUpdateResponse)
async def update_ambulance_location(request: LocationUpdateRequest):
    """
    Accept location pings from ambulance (every ~10 seconds).
    Updates the ambulance's current coordinates in Firestore.
    """
    amb_doc = ambulances_ref().document(request.ambulance_id).get()
    if not amb_doc.exists:
        raise HTTPException(status_code=404, detail="Ambulance not found")

    ambulances_ref().document(request.ambulance_id).update({
        "current_lat": request.lat,
        "current_lng": request.lng
    })

    return LocationUpdateResponse(success=True)
