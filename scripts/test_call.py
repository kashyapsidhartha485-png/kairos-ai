"""
Kairos AI — Hospital Verification Call
"""
import os, sys, time, json
import requests as http_requests
from dotenv import load_dotenv
load_dotenv()
from twilio.rest import Client

client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

print("=" * 60)
print("  KAIROS AI — Hospital Verification Call")
print("=" * 60)

twiml = (
    '<Response>'
    '<Say voice="alice" language="en-IN">'
    'This is Kairos Emergency AI dispatch. '
    'We have a 22 year old male patient presenting with acute myocardial infarction, '
    'suspected ST elevation MI. Patient is hemodynamically unstable with blood pressure '
    '80 over 50 and oxygen saturation at 89 percent. '
    'Patient requires immediate ICU admission with cardiac catheterization lab access. '
    'Does your facility have an ICU bed with cath lab availability? '
    'Please say Yes or No after the beep.'
    '</Say>'
    '<Record maxLength="5" playBeep="true" trim="trim-silence"/>'
    '<Say voice="alice">Thank you. Our ambulance team has been updated. Goodbye.</Say>'
    '</Response>'
)

call = client.calls.create(to="+917439580798", from_=os.getenv("TWILIO_PHONE_NUMBER"), twiml=twiml)
print(f"  Call SID: {call.sid}")
print(f"  Say YES or NO after the beep!\n")

for i in range(45):
    call = client.calls(call.sid).fetch()
    if i % 5 == 0: print(f"  ... {call.status}")
    if call.status in ("completed", "failed", "busy", "no-answer", "canceled"): break
    time.sleep(2)

print(f"\n  Call {call.status} ({call.duration}s)")
if call.status != "completed": sys.exit(1)

print("  Fetching recording...")
time.sleep(5)
recordings = client.recordings.list(call_sid=call.sid)
if not recordings:
    print("  No recording found.")
    sys.exit(1)

rec = recordings[0]
url = f"https://api.twilio.com/2010-04-01/Accounts/{os.getenv('TWILIO_ACCOUNT_SID')}/Recordings/{rec.sid}.mp3"
audio = http_requests.get(url, auth=(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))).content
print(f"  Recording: {rec.duration}s, {len(audio)} bytes")

print("\n  Gemini AI analyzing response...")
from google import genai
from google.genai import types
gemini = genai.Client(api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
response = gemini.models.generate_content(
    model="gemini-2.5-flash",
    contents=[types.Content(parts=[
        types.Part(text='Analyze this hospital phone response. We asked about ICU bed + cath lab availability. Return JSON: {"transcript":"exact words","bed_available":true/false,"confidence":"high/medium/low","language":"en/hi/kn","summary":"one line"}'),
        types.Part(inline_data=types.Blob(mime_type="audio/mp3", data=audio))
    ])],
    config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json")
)
result = json.loads(response.text)

print("\n" + "=" * 60)
print("  GEMINI AI RESULT")
print("=" * 60)
print(f"  Transcript:    {result.get('transcript')}")
print(f"  Bed Available: {result.get('bed_available')}")
print(f"  Confidence:    {result.get('confidence')}")
print(f"  Language:      {result.get('language')}")
print(f"  Summary:       {result.get('summary')}")
print("=" * 60)
