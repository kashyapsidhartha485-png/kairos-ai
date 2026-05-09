"""
Kairos AI — Triage Agent (Google ADK)
Framework: google-adk (Google Agent Development Kit)

Uses LlmAgent to analyze patient symptoms and determine:
- Emergency type (cardiac, trauma, neurological, etc.)
- Bed type needed (ICU, general, trauma, ventilator)
- Specialist needed
- Urgency level
"""
import json
import traceback
from google.adk.agents import LlmAgent
from app.agents.agent_base import run_agent
from app.services.firebase_client import patient_conditions_ref, emergencies_ref, users_ref
from app.services.gemini_client import gemini_json_call


# ──────────────────────────────────────────────
# TOOLS — Gemini can call these autonomously
# ──────────────────────────────────────────────

def get_patient_medical_history(emergency_id: str) -> dict:
    """Look up the patient's pre-registered medical history from the database.
    This includes existing conditions, allergies, and current medications.
    ALWAYS call this first — existing conditions change the triage urgency.
    
    Args:
        emergency_id: The emergency document ID to look up the patient
        
    Returns:
        dict with patient medical history or indication that patient is unidentified
    """
    try:
        e_doc = emergencies_ref().document(emergency_id).get()
        if not e_doc.exists:
            return {"status": "no_emergency_found"}
        emergency = e_doc.to_dict()
        patient_id = emergency.get("patient_id")
        if not patient_id:
            return {"status": "patient_not_identified", "note": "No pre-registered medical history available. Triage based on symptoms only."}
        p_doc = users_ref().document(patient_id).get()
        if not p_doc.exists:
            return {"status": "patient_record_missing"}
        patient = p_doc.to_dict()
        return {
            "status": "found",
            "name": patient.get("name"),
            "age": patient.get("age"),
            "blood_group": patient.get("blood_group"),
            "existing_conditions": patient.get("conditions"),
            "allergies": patient.get("allergies"),
            "current_medications": patient.get("medications")
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def save_triage_result(
    condition_id: str,
    condition_summary: str,
    emergency_type: str,
    bed_type_needed: str,
    specialist_needed: str,
    urgency: str,
    additional_notes: str
) -> dict:
    """Save the finalized triage assessment to the database. Call this once you've made your decision.
    
    Args:
        condition_id: The patient condition document ID
        condition_summary: Brief summary of the patient's condition
        emergency_type: Type of emergency (cardiac, trauma, neurological, respiratory, other)
        bed_type_needed: Required bed type (ICU, general, trauma, ventilator)
        specialist_needed: Type of specialist needed (cardiologist, neurologist, etc.) or 'none'
        urgency: Urgency level (critical, high, medium)
        additional_notes: Any warnings, allergy risks, or medication interactions
        
    Returns:
        dict confirming the triage was saved
    """
    triage_result = {
        "condition_summary": condition_summary,
        "emergency_type": emergency_type,
        "bed_type_needed": bed_type_needed,
        "specialist_needed": specialist_needed,
        "urgency": urgency,
        "additional_notes": additional_notes
    }
    try:
        patient_conditions_ref().document(condition_id).update({"triage_result": triage_result})
        return {"saved": True, "triage_result": triage_result}
    except Exception as e:
        return {"saved": False, "error": str(e)}


# ──────────────────────────────────────────────
# TRIAGE AGENT DEFINITION (Google ADK)
# ──────────────────────────────────────────────

TRIAGE_INSTRUCTION = """You are the Kairos AI Triage Agent. You analyze emergency patient symptoms to determine the appropriate medical response.

YOUR PROCESS:
1. FIRST call get_patient_medical_history to check if this patient has pre-registered conditions, allergies, or medications
2. Read the companion's symptom description carefully
3. Cross-reference symptoms with the patient's medical history:
   - Chest pain + cardiac history → urgency = CRITICAL, need cardiologist
   - Head injury + blood thinner medications → urgency = CRITICAL, need neurosurgeon
   - Breathing difficulty → check if ventilator bed needed
   - "Semi-conscious" or "unconscious" → usually CRITICAL
4. Check for medication interaction risks and allergy warnings
5. Call save_triage_result with your final assessment

URGENCY GUIDELINES:
- CRITICAL: Life-threatening, needs immediate intervention (cardiac arrest, stroke, severe trauma)
- HIGH: Serious but stable (broken bones, deep cuts, severe pain)
- MEDIUM: Needs medical attention but not immediately life-threatening

ALWAYS cross-reference with patient history. A "simple" chest pain becomes CRITICAL if the patient has cardiac history.
"""

triage_agent = LlmAgent(
    model="gemini-2.0-flash",
    name="triage_agent",
    description="Analyzes patient symptoms and medical history to determine emergency type, bed type, specialist, and urgency.",
    instruction=TRIAGE_INSTRUCTION,
    tools=[
        get_patient_medical_history,
        save_triage_result
    ]
)


# ──────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────

async def extract(condition_text: str, condition_id: str = None, emergency_id: str = None) -> dict:
    """
    Run the Google ADK triage agent to analyze patient symptoms.
    """
    task = f"Triage this patient based on these symptoms:\n\n{condition_text}"
    if emergency_id:
        task += f"\n\nEmergency ID: {emergency_id} (use this to check patient medical history)"
    if condition_id:
        task += f"\nCondition document ID: {condition_id} (use this when saving triage result)"

    try:
        result = await run_agent(
            agent=triage_agent,
            user_message=task,
            user_id=f"triage_{emergency_id or 'unknown'}",
            session_id=f"triage_session_{condition_id or 'unknown'}"
        )
        print(f"[Triage Agent] Complete: {result.get('response', '')[:200]}")
        return {"response": result.get("response", "")}

    except Exception as e:
        print(f"[Triage Agent] ADK error, falling back to direct Gemini call: {e}")
        traceback.print_exc()
        return await _fallback_extract(condition_text, condition_id)


async def _fallback_extract(condition_text: str, condition_id: str = None) -> dict:
    """Fallback: direct Gemini call if the ADK agent loop fails."""
    prompt = """Extract medical triage data and return JSON with:
    condition_summary, emergency_type (cardiac/trauma/neurological/respiratory/other),
    bed_type_needed (ICU/general/trauma/ventilator), specialist_needed,
    urgency (critical/high/medium), additional_notes"""
    try:
        result = await gemini_json_call(prompt, condition_text)
        if condition_id:
            patient_conditions_ref().document(condition_id).update({"triage_result": result})
        return result
    except Exception:
        return {
            "condition_summary": condition_text,
            "emergency_type": "other",
            "bed_type_needed": "general",
            "urgency": "high"
        }
