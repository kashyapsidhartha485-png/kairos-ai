"""
Kairos AI — Orchestrator Agent (Google ADK)
Framework: google-adk (Google Agent Development Kit)

This is the CORE agent — it routes patients to the best hospital.
Uses Google ADK's LlmAgent with tools that Gemini calls autonomously.
"""
import math
import time
import json
from datetime import datetime, timezone, timedelta
from google.adk.agents import LlmAgent
from app.agents.agent_base import run_agent
from app.services.firebase_client import (
    emergencies_ref, hospitals_ref, patient_conditions_ref,
    ambulances_ref, emergency_events_ref, hospital_verifications_ref
)
from app.agents import closer_agent


# ──────────────────────────────────────────────
# TOOLS — Python functions Gemini can call
# (Google ADK auto-discovers these from the agent's tools list)
# ──────────────────────────────────────────────

def get_nearby_hospitals(emergency_lat: float, emergency_lng: float, limit: int = 5) -> dict:
    """Fetch hospitals near the emergency location sorted by distance.
    
    Args:
        emergency_lat: Latitude of the emergency
        emergency_lng: Longitude of the emergency
        limit: Maximum number of hospitals to return
    
    Returns:
        dict with list of hospitals and their details
    """
    all_hospitals = []
    for doc in hospitals_ref().stream():
        h = doc.to_dict()
        h["id"] = doc.id
        h_lat = h.get("lat", 0)
        h_lng = h.get("lng", 0)
        dist_km = round(math.sqrt((h_lat - emergency_lat) ** 2 + (h_lng - emergency_lng) ** 2) * 111, 2)
        h["distance_km"] = dist_km
        # Clean non-serializable fields
        for key in list(h.keys()):
            if not isinstance(h[key], (str, int, float, bool, list, dict, type(None))):
                h[key] = str(h[key])
        all_hospitals.append(h)

    all_hospitals.sort(key=lambda x: x["distance_km"])
    results = all_hospitals[:limit]
    return {"hospitals": results, "total_found": len(all_hospitals)}


def get_triage_result(emergency_id: str) -> dict:
    """Fetch the AI triage result for this emergency to understand what the patient needs.
    
    Args:
        emergency_id: The emergency document ID
        
    Returns:
        dict with triage information including emergency_type, bed_type_needed, urgency
    """
    for doc in patient_conditions_ref().where("emergency_id", "==", emergency_id).limit(1).stream():
        data = doc.to_dict()
        triage = data.get("triage_result")
        if triage:
            return {"status": "found", "triage": triage}
    return {"status": "no_triage", "triage": {"emergency_type": "unknown", "bed_type_needed": "general", "urgency": "high"}}


def check_hospital_beds(hospital_id: str, bed_type: str) -> dict:
    """Check if a specific hospital has the required bed type available.
    
    Args:
        hospital_id: The hospital document ID to check
        bed_type: Type of bed needed (ICU, general, trauma, ventilator)
        
    Returns:
        dict with bed availability, method used, and confidence level
    """
    h_doc = hospitals_ref().document(hospital_id).get()
    if not h_doc.exists:
        return {"error": f"Hospital {hospital_id} not found"}

    h = h_doc.to_dict()

    # Determine data freshness
    last_updated = h.get("last_updated")
    is_stale = True
    if last_updated:
        if isinstance(last_updated, str):
            try:
                updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                is_stale = (datetime.now(timezone.utc) - updated_dt).total_seconds() > 1800
            except ValueError:
                is_stale = True

    # Check bed count based on type
    bed_type_lower = bed_type.lower()
    if "icu" in bed_type_lower:
        bed_count = h.get("icu_beds", 0)
    elif "ventilator" in bed_type_lower:
        bed_count = h.get("ventilator_beds", 0)
    else:
        bed_count = h.get("general_beds", 0)

    method = "digital_fresh" if not is_stale else "digital_stale"
    confidence = "high" if not is_stale else "medium"

    result = {
        "hospital_id": hospital_id,
        "hospital_name": h.get("name"),
        "bed_type_checked": bed_type,
        "beds_available": bed_count,
        "bed_available": bed_count > 0,
        "method": method,
        "confidence": confidence,
        "specializations": h.get("specializations", []),
        "note": "Data is stale (>30 min old)" if is_stale else "Data is fresh"
    }

    # Store verification record
    hospital_verifications_ref().add({
        "emergency_id": "current",
        "hospital_id": hospital_id,
        "method": method,
        "bed_available": result["bed_available"],
        "confidence": confidence,
        "raw_response": json.dumps(result, default=str),
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return result


def get_drive_time(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> dict:
    """Calculate actual driving time between two points using Google Maps.
    
    Args:
        origin_lat: Starting latitude (ambulance position)
        origin_lng: Starting longitude
        dest_lat: Destination latitude (hospital)
        dest_lng: Destination longitude
        
    Returns:
        dict with estimated driving time in minutes
    """
    try:
        from app.services.maps_client import get_single_eta
        eta = get_single_eta(origin_lat, origin_lng, dest_lat, dest_lng)
        return {"eta_minutes": eta, "method": "google_maps"}
    except Exception as e:
        dist_km = math.sqrt((origin_lat - dest_lat)**2 + (origin_lng - dest_lng)**2) * 111
        est_min = round(dist_km / 0.5, 1)
        return {"eta_minutes": est_min, "method": "estimated", "note": f"Maps API error: {str(e)}"}


def select_hospital(hospital_id: str, hospital_name: str, reason: str, emergency_id: str) -> dict:
    """FINAL DECISION: Call this exactly once to commit your hospital choice.
    
    Args:
        hospital_id: The chosen hospital's document ID
        hospital_name: The chosen hospital's name
        reason: A clear one-sentence explanation of why this hospital was chosen
        emergency_id: The emergency document ID
        
    Returns:
        dict confirming the selection was committed
    """
    emergencies_ref().document(emergency_id).update({
        "chosen_hospital_id": hospital_id,
        "routing_status": "routing_complete",
        "scoring_reason": reason,
        "status": "routed"
    })
    return {
        "committed": True,
        "hospital_id": hospital_id,
        "hospital_name": hospital_name,
        "reason": reason
    }


def update_routing_status(emergency_id: str, status: str) -> dict:
    """Update the routing status so the bystander's app can show progress.
    
    Args:
        emergency_id: The emergency document ID
        status: Current status (e.g., 'checking_hospitals', 'evaluating_options', 'routing_complete')
        
    Returns:
        dict confirming the status was updated
    """
    emergencies_ref().document(emergency_id).update({"routing_status": status})
    return {"updated": True, "status": status}


# ──────────────────────────────────────────────
# ORCHESTRATOR AGENT DEFINITION
# ──────────────────────────────────────────────

ORCHESTRATOR_INSTRUCTION = """You are the Kairos AI Hospital Routing Agent. Your critical job is to find the BEST hospital for an emergency patient being transported by ambulance.

YOUR PROCESS:
1. First call get_triage_result to understand what the patient needs (bed type, specialist, urgency)
2. Call update_routing_status with status "checking_hospitals"
3. Call get_nearby_hospitals to find hospitals near the emergency
4. For EACH hospital (starting with closest), call check_hospital_beds to verify bed availability
5. For hospitals WITH available beds, call get_drive_time from the ambulance to the hospital
6. DECIDE: Pick the hospital that has the right bed type AND is fastest to reach
7. If two hospitals are within 5 minutes drive time, prefer the one with a matching specialist
8. Call select_hospital with your final choice and a clear reason

RULES:
- NEVER select a hospital without checking beds first
- Always check at least 3 hospitals before deciding (if 3 are available)
- If NO hospital has the right bed type, pick the closest one anyway and note this
- You MUST call select_hospital exactly once as your final action
- After selecting, summarize your decision as JSON with: chosen_hospital_id, chosen_hospital_name, reason, hospitals_evaluated, confidence
"""

orchestrator_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="orchestrator_agent",
    description="Routes emergency patients to the best available hospital by checking bed availability and drive times.",
    instruction=ORCHESTRATOR_INSTRUCTION,
    tools=[
        get_nearby_hospitals,
        get_triage_result,
        check_hospital_beds,
        get_drive_time,
        select_hospital,
        update_routing_status
    ]
)


# ──────────────────────────────────────────────
# PUBLIC API — called by the condition endpoint
# ──────────────────────────────────────────────

async def run(emergency_id: str, exclude_hospital_ids: list = None):
    """
    Run the agentic hospital routing loop using Google ADK.
    
    The agent autonomously:
    1. Fetches triage data
    2. Finds nearby hospitals
    3. Checks each hospital's bed availability
    4. Calculates drive times
    5. Reasons about the best choice
    6. Commits the decision
    """
    if exclude_hospital_ids is None:
        exclude_hospital_ids = []

    start_time = time.time()
    print(f"\n{'='*60}")
    print(f"[Orchestrator Agent] Starting ADK routing for {emergency_id}")
    print(f"{'='*60}")

    # Get emergency context
    emergency_doc = emergencies_ref().document(emergency_id).get()
    if not emergency_doc.exists:
        print(f"[Orchestrator Agent] Emergency {emergency_id} not found!")
        return
    emergency = emergency_doc.to_dict()

    # Get ambulance location
    amb_lat = emergency.get("bystander_lat", 0)
    amb_lng = emergency.get("bystander_lng", 0)
    ambulance_id = emergency.get("ambulance_id")
    if ambulance_id:
        amb_doc = ambulances_ref().document(ambulance_id).get()
        if amb_doc.exists:
            amb = amb_doc.to_dict()
            amb_lat = amb.get("current_lat", amb_lat)
            amb_lng = amb.get("current_lng", amb_lng)

    # Build the task for the agent
    task = (
        f"Route emergency '{emergency_id}' to the best hospital.\n"
        f"Emergency location: lat={emergency.get('bystander_lat')}, lng={emergency.get('bystander_lng')}\n"
        f"Ambulance location: lat={amb_lat}, lng={amb_lng}\n"
    )
    if exclude_hospital_ids:
        task += f"EXCLUDE these hospitals (already tried, no beds): {exclude_hospital_ids}\n"

    # Run the agent via Google ADK
    result = await run_agent(
        agent=orchestrator_agent,
        user_message=task,
        user_id=f"emergency_{emergency_id}",
        session_id=f"routing_{emergency_id}"
    )

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"[Orchestrator Agent] Completed in {elapsed:.2f}s")
    print(f"{'='*60}\n")

    # Execute the closer agent
    emergency_doc = emergencies_ref().document(emergency_id).get()
    if emergency_doc.exists:
        emergency = emergency_doc.to_dict()
        chosen_id = emergency.get("chosen_hospital_id")
        if chosen_id:
            h_doc = hospitals_ref().document(chosen_id).get()
            if h_doc.exists:
                winning_hospital = h_doc.to_dict()
                winning_hospital["id"] = chosen_id
                winning_hospital["reason"] = emergency.get("scoring_reason", "AI agent selected this hospital")
                await closer_agent.close(
                    winning_hospital=winning_hospital,
                    emergency=emergency,
                    emergency_id=emergency_id
                )

    # Log the agent execution
    emergency_events_ref().add({
        "emergency_id": emergency_id,
        "event_type": "routing_complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "total_time_seconds": round(elapsed, 2),
            "framework": "google-adk",
            "agent_response": result.get("response", "")[:500]
        }
    })


async def rerun(emergency_id: str, exclude_hospital_id: str):
    """Re-run routing excluding a hospital that declined."""
    print(f"[Orchestrator Agent] Re-routing, excluding {exclude_hospital_id}")
    emergency_doc = emergencies_ref().document(emergency_id).get()
    if not emergency_doc.exists:
        return
    emergency = emergency_doc.to_dict()
    existing = emergency.get("excluded_hospitals", [])
    existing.append(exclude_hospital_id)
    emergencies_ref().document(emergency_id).update({
        "excluded_hospitals": existing,
        "status": "active",
        "routing_status": "re_routing"
    })
    await run(emergency_id, exclude_hospital_ids=existing)
