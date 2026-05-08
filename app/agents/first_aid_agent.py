"""
Kairos AI — First Aid Agent
Generates condition-aware first aid instructions using Gemini.
PRD Section 10.3
"""
from app.services.gemini_client import gemini_json_call


FIRST_AID_SYSTEM_PROMPT = """You are a first aid guidance AI. Based on this patient's 
medical card, generate condition-aware first aid instructions for a bystander. 
Return JSON with these exact fields:
- dos: array of strings (things the bystander SHOULD do)
- donts: array of strings (things the bystander should NOT do)
- cpr_needed: boolean (whether CPR may be needed based on conditions)

Be specific and actionable. Consider the patient's conditions, allergies, and medications 
when giving advice. Keep instructions simple enough for a non-medical person."""


async def generate(patient: dict) -> dict:
    """
    Generate first aid guidance based on patient's medical card.
    
    Args:
        patient: dict with keys name, conditions, allergies, medications
        
    Returns:
        dict with dos, donts, cpr_needed
    """
    user_prompt = (
        f"Patient: {patient.get('name', 'Unknown')}, "
        f"Age: {patient.get('age', 'Unknown')}, "
        f"Blood Group: {patient.get('blood_group', 'Unknown')}, "
        f"Conditions: {patient.get('conditions', 'None reported')}, "
        f"Allergies: {patient.get('allergies', 'None reported')}, "
        f"Medications: {patient.get('medications', 'None reported')}"
    )

    try:
        result = await gemini_json_call(
            system_prompt=FIRST_AID_SYSTEM_PROMPT,
            user_prompt=user_prompt
        )

        # Ensure expected fields exist
        return {
            "dos": result.get("dos", ["Keep patient calm", "Monitor breathing"]),
            "donts": result.get("donts", ["Do not move the patient unnecessarily"]),
            "cpr_needed": result.get("cpr_needed", False)
        }

    except Exception as e:
        print(f"[First Aid Agent] Error: {e}")
        # Fallback generic guidance
        return {
            "dos": [
                "Keep the patient calm and still",
                "Monitor breathing and pulse",
                "Call for help if situation worsens",
                "Keep airways clear"
            ],
            "donts": [
                "Do not move the patient unnecessarily",
                "Do not give food or water",
                "Do not leave the patient alone"
            ],
            "cpr_needed": False
        }
