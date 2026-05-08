"""
Kairos AI — Voice Agent
Handles automated hospital verification calls using
Google TTS → Twilio Voice → Google STT → Gemini parsing.
PRD Section 7.4 (Voice Agent)
"""
import os
import traceback
from app.services.gemini_client import gemini_json_call
from app.services.twilio_client import make_voice_call, send_sms


VOICE_PARSE_SYSTEM_PROMPT = """You are parsing a hospital receptionist's spoken response. 
We asked about bed availability for an emergency patient. 
Parse what they said into JSON with these exact fields:
- bed_available: boolean (true if they confirmed a bed is available)
- confidence: string (high/medium/low — based on how clearly they responded)
- receptionist_said_exactly: string (what they said verbatim)
- follow_up_needed: boolean (true if the response was unclear or ambiguous)

Handle responses in Hindi, English, and Kannada. 
"Haan" / "हाँ" / "ಹೌದು" = yes.
"Nahi" / "नहीं" / "ಇಲ್ಲ" = no."""


async def call(hospital: dict, triage_result: dict) -> dict:
    """
    Make an automated verification call to a hospital.
    
    For MVP/demo: This sends an SMS instead of a full voice call
    since the TTS→Twilio→STT pipeline requires a public callback URL.
    The full voice pipeline will be enabled when ngrok is running.
    
    Args:
        hospital: dict with name, phone, etc.
        triage_result: dict with emergency_type, bed_type_needed, etc.
        
    Returns:
        dict with bed_available, confidence, method, raw_response
    """
    hospital_name = hospital.get("name", "Hospital")
    hospital_phone = hospital.get("phone", "")
    emergency_type = triage_result.get("emergency_type", "emergency")
    bed_type = triage_result.get("bed_type_needed", "ICU")

    print(f"[Voice Agent] Initiating call to {hospital_name} ({hospital_phone})")

    if not hospital_phone:
        print(f"[Voice Agent] No phone number for {hospital_name}, skipping call")
        return {
            "bed_available": False,
            "confidence": "low",
            "method": "voice_call",
            "raw_response": "No phone number available for this hospital.",
            "follow_up_needed": True
        }

    try:
        # For demo: use Twilio SMS as a simplified verification
        # In production, this would be the full TTS→Voice→STT pipeline
        backend_url = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")

        script = (
            f"KAIROS AI EMERGENCY DISPATCH\n\n"
            f"We have a {emergency_type} patient en route.\n"
            f"Do you have an {bed_type} bed available?\n\n"
            f"Reply YES or NO to this number."
        )

        # Send verification SMS
        try:
            send_sms(to=hospital_phone, body=script)
        except Exception as sms_err:
            print(f"[Voice Agent] SMS fallback also failed: {sms_err}")

        # For demo purposes, try Twilio voice call with TwiML
        twiml_url = f"{backend_url}/api/twilio/hospital-verify?hospital_id={hospital.get('id')}&emergency_type={emergency_type}&bed_type={bed_type}"

        try:
            call_sid = make_voice_call(to=hospital_phone, twiml_url=twiml_url)
            print(f"[Voice Agent] Call placed to {hospital_name}, SID: {call_sid}")
        except Exception as call_err:
            print(f"[Voice Agent] Voice call failed: {call_err}")

        # Return pending result — will be updated by callback
        return {
            "bed_available": None,  # Will be updated by recording callback
            "confidence": "pending",
            "method": "voice_call",
            "raw_response": f"Call initiated to {hospital_name}. Awaiting response.",
            "call_status": "in_progress"
        }

    except Exception as e:
        print(f"[Voice Agent] Error calling {hospital_name}: {e}")
        traceback.print_exc()
        return {
            "bed_available": False,
            "confidence": "low",
            "method": "voice_call",
            "raw_response": f"Call failed: {str(e)}",
            "follow_up_needed": True
        }


async def parse_recording_transcript(transcript: str) -> dict:
    """
    Parse a hospital receptionist's transcribed response using Gemini.
    
    Args:
        transcript: Text transcribed from the recording
        
    Returns:
        dict with bed_available, confidence, receptionist_said_exactly, follow_up_needed
    """
    try:
        result = await gemini_json_call(
            system_prompt=VOICE_PARSE_SYSTEM_PROMPT,
            user_prompt=transcript
        )
        return result
    except Exception as e:
        print(f"[Voice Agent] Transcript parsing error: {e}")
        return {
            "bed_available": False,
            "confidence": "low",
            "receptionist_said_exactly": transcript,
            "follow_up_needed": True
        }
