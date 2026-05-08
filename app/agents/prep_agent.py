"""
Kairos AI — Pre-Arrival Prep Agent
Generates preparation instructions for ambulance crew en route.
PRD Section 8.3
"""
from app.services.gemini_client import gemini_json_call


PREP_SYSTEM_PROMPT = """You are advising an ambulance crew en route to a patient. 
Based on the medical card below, list the physical preparations they should make 
in the ambulance right now. Return JSON with this exact field:
- preparations: array of strings (specific actionable prep steps)

Consider the patient's known conditions, blood group, allergies, and medications.
Be specific about equipment, medications to prepare, and precautions.
Limit to 5-8 most important preparations."""


async def generate(patient: dict, emergency: dict = None) -> list:
    """
    Generate pre-arrival preparation instructions for ambulance crew.
    
    Args:
        patient: dict with medical card info
        emergency: dict with emergency details (optional)
        
    Returns:
        List of preparation instruction strings
    """
    user_prompt = (
        f"Patient: {patient.get('name', 'Unknown')}, "
        f"Age: {patient.get('age', 'Unknown')}, "
        f"Blood Group: {patient.get('blood_group', 'Unknown')}, "
        f"Conditions: {patient.get('conditions', 'None reported')}, "
        f"Allergies: {patient.get('allergies', 'None reported')}, "
        f"Medications: {patient.get('medications', 'None reported')}"
    )

    if emergency and emergency.get("bystander_notes"):
        user_prompt += f"\nScene notes: {emergency['bystander_notes']}"

    try:
        result = await gemini_json_call(
            system_prompt=PREP_SYSTEM_PROMPT,
            user_prompt=user_prompt
        )
        return result.get("preparations", [])

    except Exception as e:
        print(f"[Prep Agent] Error: {e}")
        return [
            "Prepare standard trauma kit",
            "Have oxygen supply ready",
            "Prepare IV line setup",
            "Ready the stretcher"
        ]
