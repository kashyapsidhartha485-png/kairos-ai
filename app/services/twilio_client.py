"""
Kairos AI — Twilio Client
Wrapper for Twilio SMS and Voice calls.
"""
import os
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_twilio_client() -> Client:
    """Get the Twilio client (singleton)."""
    global _client
    if _client is not None:
        return _client

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    if not account_sid or not auth_token:
        raise ValueError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set.")

    _client = Client(account_sid, auth_token)
    return _client


def send_sms(to: str, body: str) -> str:
    """
    Send an SMS via Twilio.
    
    Returns: Message SID
    """
    client = get_twilio_client()
    from_number = os.getenv("TWILIO_PHONE_NUMBER")

    message = client.messages.create(
        body=body,
        from_=from_number,
        to=to
    )

    return message.sid


def make_voice_call(to: str, twiml_url: str) -> str:
    """
    Place a voice call via Twilio using a TwiML URL.
    
    Args:
        to: Phone number to call
        twiml_url: URL returning TwiML instructions
        
    Returns: Call SID
    """
    client = get_twilio_client()
    from_number = os.getenv("TWILIO_PHONE_NUMBER")

    call = client.calls.create(
        url=twiml_url,
        to=to,
        from_=from_number,
        record=True,
        recording_status_callback=f"{os.getenv('BACKEND_BASE_URL')}/api/twilio/recording-callback",
        recording_status_callback_method="POST"
    )

    return call.sid


def generate_hospital_call_twiml(audio_url: str) -> str:
    """
    Generate TwiML XML for a hospital verification call.
    Plays the TTS audio, then records the response.
    """
    response = VoiceResponse()
    response.play(audio_url)
    response.record(
        max_length=10,
        action=f"{os.getenv('BACKEND_BASE_URL')}/api/twilio/recording-complete",
        transcribe=False
    )
    return str(response)
