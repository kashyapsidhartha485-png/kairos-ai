from dotenv import load_dotenv
load_dotenv()
from twilio.rest import Client
import os

client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

try:
    call = client.calls.create(
        to="+917439580798",
        from_=os.getenv("TWILIO_PHONE_NUMBER"),
        twiml='<Response><Say voice="alice">Hello! This is a test call from Kairos Emergency A.I. The system is working correctly. Goodbye!</Say></Response>'
    )
    print(f"Call placed! SID: {call.sid}")
    print(f"Status: {call.status}")
except Exception as e:
    print(f"Error: {e}")
