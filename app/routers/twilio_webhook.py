"""
Kairos AI — Twilio Webhook Router
Handles real-time callbacks from Twilio:
  - /api/twilio/voice-prompt  → TwiML to ask hospital about bed availability
  - /api/twilio/gather-result → Receives transcribed speech from hospital
"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Form, Request
from fastapi.responses import Response

from app.services.gemini_client import gemini_json_call
from app.services.firebase_client import hospital_verifications_ref, emergencies_ref

router = APIRouter(prefix="/api/twilio", tags=["Twilio Webhooks"])


# ──────────────────────────────────────────────
# TwiML: Ask hospital + listen for response
# ──────────────────────────────────────────────

@router.post("/voice-prompt")
async def voice_prompt(request: Request):
    """
    Twilio calls this URL when the hospital picks up.
    Returns TwiML that asks the question and listens for speech.
    """
    params = request.query_params
    hospital_name = params.get("hospital_name", "your hospital")
    emergency_type = params.get("emergency_type", "emergency")
    bed_type = params.get("bed_type", "ICU")
    hospital_id = params.get("hospital_id", "")
    emergency_id = params.get("emergency_id", "")

    # Build callback URL for when Twilio finishes listening
    callback_url = str(request.url_for("gather_result"))
    callback_url += f"?hospital_id={hospital_id}&emergency_id={emergency_id}&bed_type={bed_type}"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" timeout="5" speechTimeout="auto" language="en-IN"
            action="{callback_url}" method="POST">
        <Say voice="alice" language="en-IN">
            Hello. This is Kairos Emergency AI.
            We have a {emergency_type} patient who urgently needs an {bed_type} bed.
            Is an {bed_type} bed available at {hospital_name}?
            Please say Yes or No.
        </Say>
    </Gather>
    <Say voice="alice">We did not receive a response. Goodbye.</Say>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


# ──────────────────────────────────────────────
# Callback: Process the hospital's speech
# ──────────────────────────────────────────────

PARSE_PROMPT = """You are parsing a hospital receptionist's response to: "Is an ICU bed available?"

Parse into JSON:
{
    "bed_available": true/false,
    "confidence": "high"/"medium"/"low",
    "language": "en"/"hi"/"kn",
    "summary": "one sentence"
}

Handle English, Hindi, Kannada. "Haan"/"हाँ" = yes. "Nahi"/"नहीं" = no."""


@router.post("/gather-result", name="gather_result")
async def gather_result(
    request: Request,
    SpeechResult: str = Form(default=""),
    Confidence: str = Form(default="0.0"),
):
    """
    Twilio POSTs here with the transcribed speech from the hospital.
    We use Gemini to understand the response and update Firestore.
    """
    params = request.query_params
    hospital_id = params.get("hospital_id", "")
    emergency_id = params.get("emergency_id", "")
    bed_type = params.get("bed_type", "ICU")

    print(f"[Twilio Webhook] Hospital {hospital_id} said: '{SpeechResult}' (confidence: {Confidence})")

    # Use Gemini to parse the response
    try:
        parsed = await gemini_json_call(
            system_prompt=PARSE_PROMPT,
            user_prompt=f'Hospital receptionist said: "{SpeechResult}"'
        )
    except Exception as e:
        print(f"[Twilio Webhook] Gemini parse error: {e}")
        # Fallback: simple keyword matching
        lower = SpeechResult.lower()
        parsed = {
            "bed_available": any(w in lower for w in ["yes", "haan", "available", "houdu"]),
            "confidence": "low",
            "language": "unknown",
            "summary": SpeechResult
        }

    bed_available = parsed.get("bed_available", False)

    # Store verification in Firestore
    try:
        hospital_verifications_ref().add({
            "emergency_id": emergency_id,
            "hospital_id": hospital_id,
            "method": "voice_call_realtime",
            "speech_result": SpeechResult,
            "twilio_confidence": float(Confidence),
            "bed_available": bed_available,
            "confidence": parsed.get("confidence", "medium"),
            "gemini_parsed": json.dumps(parsed, default=str),
            "bed_type_checked": bed_type,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        print(f"[Twilio Webhook] Firestore error: {e}")

    # Update emergency routing if we have an emergency_id
    if emergency_id:
        try:
            emergencies_ref().document(emergency_id).update({
                "routing_status": f"hospital_{hospital_id}_{'available' if bed_available else 'unavailable'}"
            })
        except Exception:
            pass

    print(f"[Twilio Webhook] Result: bed_available={bed_available}, confidence={parsed.get('confidence')}")

    # Respond with thank you TwiML
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Thank you for your response. Our ambulance team has been notified. Goodbye.</Say>
</Response>"""

    return Response(content=twiml, media_type="application/xml")
