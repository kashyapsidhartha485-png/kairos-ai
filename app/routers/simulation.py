"""
Kairos AI — Ambulance Simulation API
Generates waypoints along a route and updates ambulance position in Firestore.
Used by the live dashboard to show the ambulance moving on the map.
"""
import asyncio
import math
import time
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks
from app.services.firebase_client import ambulances_ref, emergencies_ref, hospitals_ref

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])


def interpolate_points(start_lat, start_lng, end_lat, end_lng, steps=20):
    """Generate intermediate GPS points between two locations."""
    points = []
    for i in range(steps + 1):
        t = i / steps
        lat = start_lat + (end_lat - start_lat) * t
        lng = start_lng + (end_lng - start_lng) * t
        # Add slight random variation to simulate real driving
        import random
        lat += random.uniform(-0.0003, 0.0003)
        lng += random.uniform(-0.0003, 0.0003)
        points.append({"lat": round(lat, 6), "lng": round(lng, 6)})
    return points


async def run_simulation(emergency_id: str, ambulance_id: str, speed: float = 1.0):
    """
    Simulate ambulance movement:
    Phase 1: Ambulance → Patient location
    Phase 2: Patient location → Hospital
    Updates Firestore in real-time so the dashboard can track it.
    """
    # Fetch emergency data
    emerg_doc = emergencies_ref().document(emergency_id).get()
    if not emerg_doc.exists:
        print(f"[Simulation] Emergency {emergency_id} not found")
        return
    emergency = emerg_doc.to_dict()

    # Fetch ambulance data
    amb_doc = ambulances_ref().document(ambulance_id).get()
    if not amb_doc.exists:
        print(f"[Simulation] Ambulance {ambulance_id} not found")
        return
    ambulance = amb_doc.to_dict()

    patient_lat = emergency.get("bystander_lat", 12.9716)
    patient_lng = emergency.get("bystander_lng", 77.5946)
    amb_lat = ambulance.get("current_lat", 12.9800)
    amb_lng = ambulance.get("current_lng", 77.6000)

    # Get hospital location
    hospital_id = emergency.get("chosen_hospital_id")
    hosp_lat, hosp_lng = 12.8917, 77.5963  # Default: Apollo
    hospital_name = "Hospital"
    if hospital_id:
        hosp_doc = hospitals_ref().document(hospital_id).get()
        if hosp_doc.exists:
            hosp = hosp_doc.to_dict()
            hosp_lat = hosp.get("lat", hosp_lat)
            hosp_lng = hosp.get("lng", hosp_lng)
            hospital_name = hosp.get("name", "Hospital")

    delay = 0.4 / speed  # Fast updates for demo

    # ─── PHASE 1: Ambulance → Patient (5 seconds) ───
    print(f"[Simulation] Phase 1: Ambulance → Patient")
    emergencies_ref().document(emergency_id).update({
        "simulation_phase": "en_route_to_patient",
        "simulation_status": "Ambulance dispatched"
    })
    ambulances_ref().document(ambulance_id).update({"status": "en_route"})

    waypoints_to_patient = interpolate_points(amb_lat, amb_lng, patient_lat, patient_lng, steps=8)

    for i, point in enumerate(waypoints_to_patient):
        ambulances_ref().document(ambulance_id).update({
            "current_lat": point["lat"],
            "current_lng": point["lng"],
            "heading": "to_patient",
            "progress_percent": round((i / len(waypoints_to_patient)) * 50)  # 0-50%
        })
        emergencies_ref().document(emergency_id).update({
            "ambulance_lat": point["lat"],
            "ambulance_lng": point["lng"],
            "simulation_status": f"Ambulance en route to patient ({round((i / len(waypoints_to_patient)) * 100)}%)"
        })
        await asyncio.sleep(delay)

    # ─── PATIENT PICKUP ───
    print(f"[Simulation] Patient picked up!")
    emergencies_ref().document(emergency_id).update({
        "simulation_phase": "patient_picked_up",
        "simulation_status": "Patient secured in ambulance",
        "patient_pickup_time": datetime.now(timezone.utc).isoformat()
    })
    ambulances_ref().document(ambulance_id).update({"status": "transporting"})
    await asyncio.sleep(1 / speed)

    # ─── PHASE 2: Patient → Hospital (5 seconds) ───
    print(f"[Simulation] Phase 2: Patient → {hospital_name}")
    emergencies_ref().document(emergency_id).update({
        "simulation_phase": "en_route_to_hospital",
        "simulation_status": f"Transporting patient to {hospital_name}"
    })

    waypoints_to_hospital = interpolate_points(patient_lat, patient_lng, hosp_lat, hosp_lng, steps=10)

    for i, point in enumerate(waypoints_to_hospital):
        ambulances_ref().document(ambulance_id).update({
            "current_lat": point["lat"],
            "current_lng": point["lng"],
            "heading": "to_hospital",
            "progress_percent": 50 + round((i / len(waypoints_to_hospital)) * 50)  # 50-100%
        })
        emergencies_ref().document(emergency_id).update({
            "ambulance_lat": point["lat"],
            "ambulance_lng": point["lng"],
            "simulation_status": f"En route to {hospital_name} ({round((i / len(waypoints_to_hospital)) * 100)}%)"
        })
        await asyncio.sleep(delay)

    # ─── ARRIVED ───
    print(f"[Simulation] Arrived at {hospital_name}!")
    emergencies_ref().document(emergency_id).update({
        "simulation_phase": "arrived",
        "simulation_status": f"Patient delivered to {hospital_name}",
        "arrival_time": datetime.now(timezone.utc).isoformat()
    })
    ambulances_ref().document(ambulance_id).update({
        "status": "available",
        "current_lat": hosp_lat,
        "current_lng": hosp_lng,
        "heading": "idle",
        "progress_percent": 100
    })

    # Brief pause then mark as complete (frontend polls for this phase)
    await asyncio.sleep(0.5)
    emergencies_ref().document(emergency_id).update({
        "simulation_phase": "complete",
        "simulation_status": f"Patient delivered to {hospital_name} ✅",
        "status": "completed"
    })

    print(f"[Simulation] Complete!")


@router.post("/start")
async def start_simulation(
    emergency_id: str,
    ambulance_id: str = "AMB-001",
    speed: float = 1.0,
    background_tasks: BackgroundTasks = None
):
    """Start ambulance movement simulation."""
    background_tasks.add_task(run_simulation, emergency_id, ambulance_id, speed)
    return {
        "status": "simulation_started",
        "emergency_id": emergency_id,
        "ambulance_id": ambulance_id,
        "speed": speed,
        "note": "Track at /dashboard?emergency_id=" + emergency_id
    }


@router.get("/status/{emergency_id}")
async def get_simulation_status(emergency_id: str):
    """Get current simulation state for the dashboard."""
    emerg_doc = emergencies_ref().document(emergency_id).get()
    if not emerg_doc.exists:
        return {"error": "Emergency not found"}
    emergency = emerg_doc.to_dict()

    ambulance_id = emergency.get("ambulance_id", "AMB-001")
    amb_doc = ambulances_ref().document(ambulance_id).get()
    ambulance = amb_doc.to_dict() if amb_doc.exists else {}

    hospital_id = emergency.get("chosen_hospital_id")
    hospital = {}
    if hospital_id:
        hosp_doc = hospitals_ref().document(hospital_id).get()
        hospital = hosp_doc.to_dict() if hosp_doc.exists else {}

    return {
        "emergency_id": emergency_id,
        "phase": emergency.get("simulation_phase", "waiting"),
        "status_text": emergency.get("simulation_status", "Waiting..."),
        "progress_percent": ambulance.get("progress_percent", 0),
        "ambulance": {
            "id": ambulance_id,
            "lat": ambulance.get("current_lat"),
            "lng": ambulance.get("current_lng"),
            "driver": ambulance.get("driver_name"),
            "heading": ambulance.get("heading", "idle")
        },
        "patient": {
            "lat": emergency.get("bystander_lat"),
            "lng": emergency.get("bystander_lng")
        },
        "hospital": {
            "id": hospital_id,
            "name": hospital.get("name"),
            "lat": hospital.get("lat"),
            "lng": hospital.get("lng")
        }
    }
