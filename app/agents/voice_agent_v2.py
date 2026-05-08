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
# Voice Call Script Generation (from real triage data)
# ──────────────────────────────────────────────

async def generate_call_script(hospital_name: str, triage_result: dict, patient_data: dict = None) -> str:
    """
    Generate a professional medical dispatch call script using Gemini.
    Uses actual triage data from the emergency incident.
    """
    from app.services.gemini_client import gemini_text_call

    emergency_type = triage_result.get("emergency_type", "emergency")
    bed_type = triage_result.get("bed_type_needed", "ICU")
    urgency = triage_result.get("urgency", "high")
    specialist = triage_result.get("specialist_needed", "emergency physician")
    symptoms = triage_result.get("symptoms", [])
    vitals = triage_result.get("vitals", {})

    # Patient info if available
    age = ""
    gender = ""
    conditions = ""
    if patient_data:
        age = f"{patient_data.get('age', 'unknown')} year old"
        gender = patient_data.get('gender', '')
        conditions = patient_data.get('conditions', 'none known')

    prompt = f"""Generate a 3-4 sentence hospital dispatch call script. Be professional and use proper medical terminology.

INCIDENT DATA:
- Emergency Type: {emergency_type}
- Patient: {age} {gender}
- Known Conditions: {conditions}
- Symptoms: {', '.join(symptoms) if isinstance(symptoms, list) else symptoms}
- Vitals: {json.dumps(vitals) if vitals else 'not available'}
- Bed Type Required: {bed_type}
- Specialist Needed: {specialist}
- Urgency: {urgency}
- Hospital: {hospital_name}

FORMAT:
"This is Kairos Emergency AI dispatch. [Patient description with medical details]. [What is needed]. Does your facility have [bed type] availability? Please say Yes or No."

Keep it under 30 seconds when spoken. Use proper medical terms (e.g., "acute myocardial infarction" not "heart attack", "open fracture of tibia" not "broken leg")."""

    try:
        script = await gemini_text_call(
            system_prompt="You are a professional emergency medical dispatch AI. Generate concise, clinical call scripts.",
            user_prompt=prompt
        )
        return script.strip().strip('"')
    except Exception as e:
        print(f"[Voice Agent] Script generation error: {e}")
        # Fallback to basic script
        return (
            f"This is Kairos Emergency AI dispatch. "
            f"We have a {urgency} priority {emergency_type} patient requiring {bed_type} admission "
            f"with {specialist} consultation. "
            f"Does {hospital_name} have {bed_type} availability? Please say Yes or No."
        )


# ──────────────────────────────────────────────
# Main Voice Agent — Real-time Call with Triage Data
# ──────────────────────────────────────────────

async def call(hospital: dict, triage_result: dict) -> dict:
    """
    Hospital verification call using real incident data:
    1. Gemini generates a medical dispatch script from triage data
    2. Twilio calls hospital with the script
    3. Records hospital's response
    4. Gemini analyzes the recording
    5. Returns bed availability result

    The script includes proper medical terminology based on actual patient condition.
    """
    hospital_name = hospital.get("name", "Hospital")
    hospital_phone = hospital.get("phone", "")
    hospital_id = hospital.get("id", "")
    bed_type = triage_result.get("bed_type_needed", "ICU")

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

    # Fetch patient data if emergency has a patient_id
    patient_data = None
    emergency_id = triage_result.get("emergency_id", "")
    if emergency_id:
        try:
            from app.services.firebase_client import emergencies_ref, users_ref
            emerg_doc = emergencies_ref().document(emergency_id).get()
            if emerg_doc.exists:
                emerg = emerg_doc.to_dict()
                patient_id = emerg.get("patient_id")
                if patient_id:
                    patient_doc = users_ref().document(patient_id).get()
                    if patient_doc.exists:
                        patient_data = patient_doc.to_dict()
        except Exception as e:
            print(f"[Voice Agent] Could not fetch patient data: {e}")

    # Step 1: Generate medical dispatch script from real triage data
    print(f"[Voice Agent] Generating dispatch script from triage data...")
    script = await generate_call_script(hospital_name, triage_result, patient_data)
    print(f"[Voice Agent] Script: {script[:100]}...")

    # Step 2: Place call with inline TwiML
    try:
        from twilio.rest import Client
        import xml.sax.saxutils as saxutils

        twilio_client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN")
        )

        # Escape script for XML
        safe_script = saxutils.escape(script)

        twiml = (
            f'<Response>'
            f'<Say voice="alice" language="en-IN">{safe_script}</Say>'
            f'<Record maxLength="5" playBeep="true" trim="trim-silence"/>'
            f'<Say voice="alice">Thank you. Our ambulance team has been updated. Goodbye.</Say>'
            f'</Response>'
        )

        twilio_call = twilio_client.calls.create(
            to=hospital_phone,
            from_=os.getenv("TWILIO_PHONE_NUMBER"),
            twiml=twiml,
            timeout=30
        )

        print(f"[Voice Agent] Call placed! SID: {twilio_call.sid}")

        # Poll for completion
        for i in range(45):
            twilio_call = twilio_client.calls(twilio_call.sid).fetch()
            if twilio_call.status in ("completed", "failed", "busy", "no-answer", "canceled"):
                break
            await asyncio.sleep(2)

        print(f"[Voice Agent] Call {twilio_call.status} ({twilio_call.duration}s)")

        if twilio_call.status != "completed":
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "bed_available": None,
                "confidence": "low",
                "method": "voice_call",
                "raw_response": f"Call {twilio_call.status}",
                "follow_up_needed": True,
                "time_taken_ms": elapsed_ms
            }

        # Step 3: Fetch recording
        await asyncio.sleep(3)
        recordings = twilio_client.recordings.list(call_sid=twilio_call.sid)

        if not recordings:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "bed_available": None,
                "confidence": "low",
                "method": "voice_call",
                "raw_response": "No response recorded from hospital.",
                "follow_up_needed": True,
                "time_taken_ms": elapsed_ms
            }

        rec = recordings[0]
        rec_url = f"https://api.twilio.com/2010-04-01/Accounts/{os.getenv('TWILIO_ACCOUNT_SID')}/Recordings/{rec.sid}.mp3"

        import requests as http_requests
        audio = http_requests.get(rec_url, auth=(
            os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
        )).content

        # Step 4: Gemini analyzes the audio response
        print(f"[Voice Agent] Analyzing {len(audio)} bytes with Gemini...")
        from google import genai
        from google.genai import types

        gemini = genai.Client(api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=[types.Content(parts=[
                types.Part(text=(
                    f'Analyze this hospital phone response. We asked about {bed_type} bed availability. '
                    f'Return JSON: {{"transcript":"exact words","bed_available":true/false,'
                    f'"confidence":"high/medium/low","language":"en/hi/kn"}}'
                )),
                types.Part(inline_data=types.Blob(mime_type="audio/mp3", data=audio))
            ])],
            config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json")
        )

        result = json.loads(response.text)
        elapsed_ms = int((time.time() - start_time) * 1000)

        print(f"[Voice Agent] Result: bed={result.get('bed_available')}, "
              f"said='{result.get('transcript')}', confidence={result.get('confidence')}")

        return {
            "bed_available": result.get("bed_available"),
            "confidence": result.get("confidence", "medium"),
            "method": "voice_call",
            "raw_response": result.get("transcript", ""),
            "follow_up_needed": False,
            "time_taken_ms": elapsed_ms
        }

    except Exception as e:
        print(f"[Voice Agent] Call failed: {e}")
        elapsed_ms = int((time.time() - start_time) * 1000)
        bed_count = hospital.get("icu_beds", 0) if "icu" in bed_type.lower() else hospital.get("general_beds", 0)
        return {
            "bed_available": bed_count > 0,
            "confidence": "medium",
            "method": "digital_fallback",
            "raw_response": f"Call failed ({e}). Digital check: {bed_type} beds = {bed_count}",
            "follow_up_needed": False,
            "time_taken_ms": elapsed_ms
        }
