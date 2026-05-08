"""
Kairos AI — Scoring Agent
Uses Gemini + Distance Matrix to rank hospitals by suitability.
PRD Section 10.3
"""
from app.services.gemini_client import gemini_json_call
from app.services.maps_client import get_distance_matrix
import json


SCORING_SYSTEM_PROMPT = """You are a hospital routing agent. Pick the best hospital 
given patient needs, location, and verified availability. 

RULES (in priority order):
1. Hospital MUST have a confirmed available bed (bed_available: true). 
   Never select a hospital without a confirmed bed.
2. Among hospitals with beds, prefer the closest one by actual drive time 
   (not straight-line distance).
3. If two hospitals are within 5 minutes drive time of each other, prefer 
   the one with a specialist match for the patient's condition.

Return JSON with these exact fields:
- chosen_hospital_id: string (the ID of the best hospital)
- chosen_hospital_name: string
- reason: string (one plain-English sentence explaining the choice)
- distance_km: number (approximate distance)
- confidence: string (high/medium/low)"""


async def rank(
    hospitals_with_results: list,
    ambulance_lat: float,
    ambulance_lng: float,
    triage_result: dict
) -> dict:
    """
    Rank hospitals and select the best one for the patient.
    
    Args:
        hospitals_with_results: List of dicts with hospital info + worker results
        ambulance_lat: Current ambulance latitude
        ambulance_lng: Current ambulance longitude
        triage_result: Structured triage data from triage agent
        
    Returns:
        dict with chosen_hospital_id, chosen_hospital_name, reason, distance_km, confidence
    """
    # Get actual drive times from ambulance to each candidate hospital
    available_hospitals = [
        h for h in hospitals_with_results 
        if h.get("verification", {}).get("bed_available", False)
    ]

    if not available_hospitals:
        # No beds available anywhere — pick the closest for fallback
        available_hospitals = hospitals_with_results
        print("[Scoring Agent] WARNING: No confirmed beds. Using fallback ranking.")

    # Get drive times via Distance Matrix
    origins = [f"{ambulance_lat},{ambulance_lng}"]
    destinations = [f"{h['lat']},{h['lng']}" for h in available_hospitals]

    try:
        from app.services.maps_client import get_maps_client
        client = get_maps_client()
        matrix_result = client.distance_matrix(
            origins=origins,
            destinations=destinations,
            mode="driving",
            departure_time="now"
        )

        for i, row_element in enumerate(matrix_result["rows"][0]["elements"]):
            if row_element["status"] == "OK":
                duration = row_element.get("duration_in_traffic", row_element["duration"])
                available_hospitals[i]["drive_time_seconds"] = duration["value"]
                available_hospitals[i]["drive_time_text"] = duration["text"]
                available_hospitals[i]["distance_km"] = round(
                    row_element["distance"]["value"] / 1000, 1
                )
    except Exception as e:
        print(f"[Scoring Agent] Distance Matrix error: {e}")
        # Fallback: estimate from coordinates
        for h in available_hospitals:
            h["drive_time_seconds"] = 9999
            h["distance_km"] = 0

    # Build context for Gemini
    context = {
        "triage": triage_result,
        "ambulance_location": {"lat": ambulance_lat, "lng": ambulance_lng},
        "hospitals": [
            {
                "id": h.get("id"),
                "name": h.get("name"),
                "specializations": h.get("specializations", []),
                "verification": h.get("verification", {}),
                "drive_time_seconds": h.get("drive_time_seconds"),
                "drive_time_text": h.get("drive_time_text", "unknown"),
                "distance_km": h.get("distance_km", 0),
                "icu_beds": h.get("icu_beds", 0),
                "general_beds": h.get("general_beds", 0),
                "ventilator_beds": h.get("ventilator_beds", 0),
            }
            for h in available_hospitals
        ]
    }

    try:
        result = await gemini_json_call(
            system_prompt=SCORING_SYSTEM_PROMPT,
            user_prompt=json.dumps(context, indent=2)
        )
        return result

    except Exception as e:
        print(f"[Scoring Agent] Gemini error: {e}")
        # Fallback: pick closest hospital with available bed
        sorted_hospitals = sorted(
            available_hospitals, 
            key=lambda h: h.get("drive_time_seconds", 9999)
        )
        winner = sorted_hospitals[0]
        return {
            "chosen_hospital_id": winner.get("id"),
            "chosen_hospital_name": winner.get("name"),
            "reason": "Selected closest hospital with available bed (AI scoring unavailable).",
            "distance_km": winner.get("distance_km", 0),
            "confidence": "medium"
        }
