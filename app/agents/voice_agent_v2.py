"""
Kairos AI — Hospital Verification Voice Agent (Google Native)
=============================================================
A custom ADK-based agent that calls hospitals to verify bed availability.

Architecture:
  - Google Cloud TTS: Generates the outbound voice prompt
  - Google Cloud STT: Transcribes the hospital receptionist's response
  - Gemini 2.5 Flash: Parses and understands the response (multi-lingual)
  - Telephony Bridge: Pluggable (Twilio, Exotel, or any SIP provider)

The agent is smart enough to:
  1. Greet in the hospital's language
  2. Ask about specific bed types
  3. Handle follow-up questions
  4. Parse Yes/No in English, Hindi, and Kannada
  5. Return a structured result

PRD Section 7.4
"""
import os
import io
import json
import time
import base64
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


# ──────────────────────────────────────────────
# Google Cloud TTS (Text-to-Speech)
# ──────────────────────────────────────────────

async def generate_speech(text: str, language_code: str = "en-IN") -> bytes:
    """
    Generate speech audio from text using Google Cloud TTS.
    Returns WAV audio bytes.
    
    Supports:
      - en-IN: English (India)
      - hi-IN: Hindi
      - kn-IN: Kannada
    """
    try:
        from google.cloud import texttospeech
        
        client = texttospeech.TextToSpeechClient()
        
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.95,  # Slightly slower for clarity
            pitch=0.0
        )
        
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        print(f"[Voice Agent] TTS generated: {len(response.audio_content)} bytes ({language_code})")
        return response.audio_content
        
    except ImportError:
        print("[Voice Agent] google-cloud-texttospeech not installed, using Gemini TTS fallback")
        return await _gemini_tts_fallback(text)
    except Exception as e:
        print(f"[Voice Agent] Google TTS error: {e}, using Gemini fallback")
        return await _gemini_tts_fallback(text)


async def _gemini_tts_fallback(text: str) -> bytes:
    """Fallback: Use Gemini's built-in TTS via the genai SDK."""
    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Read this aloud naturally as a hospital emergency dispatcher: {text}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
            )
        )
        
        # Extract audio if available
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    return part.inline_data.data
        
        print("[Voice Agent] Gemini TTS produced no audio")
        return b""
    except Exception as e:
        print(f"[Voice Agent] Gemini TTS fallback error: {e}")
        return b""


# ──────────────────────────────────────────────
# Google Cloud STT (Speech-to-Text)
# ──────────────────────────────────────────────

async def transcribe_audio(audio_bytes: bytes, language_code: str = "en-IN") -> str:
    """
    Transcribe audio using Google Cloud Speech-to-Text.
    Supports multi-language recognition (English + Hindi + Kannada).
    """
    try:
        from google.cloud import speech
        
        client = speech.SpeechClient()
        
        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=8000,  # Telephony standard
            language_code=language_code,
            alternative_language_codes=["hi-IN", "kn-IN"],  # Also detect Hindi & Kannada
            enable_automatic_punctuation=True,
            model="phone_call",  # Optimized for phone audio
        )
        
        response = client.recognize(config=config, audio=audio)
        
        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript + " "
        
        transcript = transcript.strip()
        print(f"[Voice Agent] STT transcript: '{transcript}'")
        return transcript
        
    except ImportError:
        print("[Voice Agent] google-cloud-speech not installed, using Gemini STT fallback")
        return await _gemini_stt_fallback(audio_bytes)
    except Exception as e:
        print(f"[Voice Agent] Google STT error: {e}")
        return ""


async def _gemini_stt_fallback(audio_bytes: bytes) -> str:
    """Fallback: Use Gemini's multimodal capability to transcribe audio."""
    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
        
        audio_b64 = base64.b64encode(audio_bytes).decode()
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Content(parts=[
                    types.Part(text="Transcribe this phone call audio exactly. The speaker may use English, Hindi, or Kannada."),
                    types.Part(inline_data=types.Blob(mime_type="audio/wav", data=audio_bytes))
                ])
            ]
        )
        
        return response.text.strip()
    except Exception as e:
        print(f"[Voice Agent] Gemini STT fallback error: {e}")
        return ""


# ──────────────────────────────────────────────
# Gemini Response Parser (Multi-lingual)
# ──────────────────────────────────────────────

PARSE_SYSTEM_PROMPT = """You are parsing a hospital receptionist's spoken response to an emergency bed availability request.

Parse the response into JSON with these exact fields:
- bed_available: boolean (true if they confirmed a bed IS available)
- confidence: string ("high" / "medium" / "low")
- what_they_said: string (the verbatim response)
- follow_up_needed: boolean (true if the response was ambiguous)
- language_detected: string ("en" / "hi" / "kn" / "other")

IMPORTANT: Handle responses in multiple languages:
  English: "Yes" / "No" / "Available" / "Not available" / "Full"
  Hindi: "Haan" / "हाँ" / "Nahi" / "नहीं" / "Khali hai" / "Bhara hai"
  Kannada: "Houdu" / "ಹೌದು" / "Illa" / "ಇಲ್ಲ"

If the response is unclear or a question, set follow_up_needed to true.
If they say "wait" or "check", set confidence to "medium" and bed_available to null."""


async def parse_response(transcript: str) -> dict:
    """Parse a hospital receptionist's response using Gemini."""
    from app.services.gemini_client import gemini_json_call
    
    try:
        result = await gemini_json_call(
            system_prompt=PARSE_SYSTEM_PROMPT,
            user_prompt=f"Hospital receptionist said: \"{transcript}\""
        )
        return result
    except Exception as e:
        print(f"[Voice Agent] Parse error: {e}")
        return {
            "bed_available": None,
            "confidence": "low",
            "what_they_said": transcript,
            "follow_up_needed": True,
            "language_detected": "unknown"
        }


# ──────────────────────────────────────────────
# Voice Call Scripts (Multi-lingual)
# ──────────────────────────────────────────────

def generate_call_script(hospital_name: str, emergency_type: str, bed_type: str, language: str = "en") -> str:
    """Generate the voice prompt script in the appropriate language."""
    
    scripts = {
        "en": (
            f"Hello, this is an automated call from Kairos Emergency AI. "
            f"We have a {emergency_type} patient who needs an {bed_type} bed urgently. "
            f"Is an {bed_type} bed available at {hospital_name}? "
            f"Please say Yes or No."
        ),
        "hi": (
            f"Namaste, yeh Kairos Emergency AI ka automated call hai. "
            f"Humare paas ek {emergency_type} patient hai jisko {bed_type} bed chahiye urgently. "
            f"Kya {hospital_name} mein {bed_type} bed available hai? "
            f"Kripya Haan ya Na kahein."
        ),
        "kn": (
            f"Namaskara, idu Kairos Emergency AI yinda automated call. "
            f"Namage {emergency_type} patient iddare, {bed_type} bed urgently beku. "
            f"{hospital_name} alli {bed_type} bed available ide? "
            f"Dayavittu Houdu athava Illa heli."
        )
    }
    
    return scripts.get(language, scripts["en"])


# ──────────────────────────────────────────────
# Telephony Bridge (Pluggable)
# ──────────────────────────────────────────────

class TelephonyBridge:
    """
    Abstract telephony bridge. Currently supports Twilio.
    Can be swapped for Exotel, Plivo, or any SIP provider.
    """
    
    @staticmethod
    async def place_call(phone_number: str, audio_bytes: bytes, callback_url: str) -> dict:
        """
        Place a phone call and play audio. Returns call metadata.
        """
        # Try Twilio first
        try:
            from app.services.twilio_client import make_voice_call
            call_sid = make_voice_call(to=phone_number, twiml_url=callback_url)
            return {"provider": "twilio", "call_sid": call_sid, "status": "initiated"}
        except Exception as twilio_err:
            print(f"[Telephony] Twilio unavailable: {twilio_err}")
        
        # Fallback: No telephony provider available
        print(f"[Telephony] No provider available. Call to {phone_number} simulated.")
        return {
            "provider": "simulated",
            "status": "simulated",
            "note": "No telephony provider configured. Configure Twilio/Exotel in .env"
        }
    
    @staticmethod
    async def send_notification(phone_number: str, message: str) -> dict:
        """Send SMS/notification as fallback."""
        try:
            from app.services.twilio_client import send_sms
            send_sms(to=phone_number, body=message)
            return {"method": "sms", "status": "sent"}
        except Exception:
            print(f"[Telephony] SMS unavailable, notification logged only")
            return {"method": "log_only", "status": "logged", "message": message}


# ──────────────────────────────────────────────
# Main Voice Agent — The Complete Pipeline
# ──────────────────────────────────────────────

async def call(hospital: dict, triage_result: dict) -> dict:
    """
    Complete voice verification pipeline:
    1. Generate script → 2. TTS → 3. Place call → 4. Get response → 5. STT → 6. Gemini parse
    
    For demo mode (no telephony): simulates the call and returns a pending result.
    """
    hospital_name = hospital.get("name", "Hospital")
    hospital_phone = hospital.get("phone", "")
    hospital_id = hospital.get("id", "")
    emergency_type = triage_result.get("emergency_type", "emergency")
    bed_type = triage_result.get("bed_type_needed", "ICU")
    language = hospital.get("preferred_language", "en")

    start_time = time.time()
    print(f"[Voice Agent] === Starting verification call to {hospital_name} ===")

    if not hospital_phone:
        print(f"[Voice Agent] No phone number for {hospital_name}")
        return {
            "bed_available": None,
            "confidence": "low",
            "method": "voice_call",
            "raw_response": "No phone number available.",
            "follow_up_needed": True,
            "time_taken_ms": 0
        }

    # Step 1: Generate the call script
    script = generate_call_script(hospital_name, emergency_type, bed_type, language)
    print(f"[Voice Agent] Script ({language}): {script[:80]}...")

    # Step 2: Convert to speech
    audio_bytes = await generate_speech(script, f"{language}-IN")

    # Step 3: Place the call via telephony bridge
    backend_url = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
    callback_url = (
        f"{backend_url}/api/twilio/hospital-verify"
        f"?hospital_id={hospital_id}"
        f"&emergency_type={emergency_type}"
        f"&bed_type={bed_type}"
    )

    call_result = await TelephonyBridge.place_call(hospital_phone, audio_bytes, callback_url)
    
    # Also send SMS notification as backup
    sms_body = (
        f"KAIROS AI EMERGENCY\n\n"
        f"{emergency_type.upper()} patient needs {bed_type} bed.\n"
        f"Confirm at: {backend_url}/api/hospital/{hospital_id}/status\n\n"
        f"Reply YES or NO"
    )
    await TelephonyBridge.send_notification(hospital_phone, sms_body)

    elapsed_ms = int((time.time() - start_time) * 1000)

    if call_result.get("provider") == "simulated":
        # Demo mode: return result based on Firestore bed data
        print(f"[Voice Agent] Demo mode — using digital fallback for {hospital_name}")
        bed_count = hospital.get("icu_beds", 0) if "icu" in bed_type.lower() else hospital.get("general_beds", 0)
        return {
            "bed_available": bed_count > 0,
            "confidence": "medium",
            "method": "voice_simulated",
            "raw_response": f"Call simulated (no telephony). Digital check: {bed_type} beds = {bed_count}",
            "follow_up_needed": False,
            "time_taken_ms": elapsed_ms,
            "call_provider": "simulated"
        }

    # Call was placed — return pending (will be updated by webhook callback)
    return {
        "bed_available": None,
        "confidence": "pending",
        "method": "voice_call",
        "raw_response": f"Call to {hospital_name} initiated via {call_result['provider']}",
        "call_sid": call_result.get("call_sid"),
        "follow_up_needed": False,
        "time_taken_ms": elapsed_ms,
        "call_provider": call_result["provider"]
    }


async def handle_recording_callback(audio_bytes: bytes, hospital_id: str) -> dict:
    """
    Called by the telephony webhook when the hospital's response recording is ready.
    Runs the STT → Gemini parse pipeline.
    """
    print(f"[Voice Agent] Processing recording callback for hospital {hospital_id}")
    
    # Step 4: Transcribe the recording
    transcript = await transcribe_audio(audio_bytes)
    
    if not transcript:
        return {
            "bed_available": None,
            "confidence": "low",
            "what_they_said": "(could not transcribe)",
            "follow_up_needed": True
        }
    
    # Step 5: Parse with Gemini
    parsed = await parse_response(transcript)
    
    print(f"[Voice Agent] Result: bed_available={parsed.get('bed_available')}, "
          f"confidence={parsed.get('confidence')}, "
          f"language={parsed.get('language_detected')}")
    
    return parsed
