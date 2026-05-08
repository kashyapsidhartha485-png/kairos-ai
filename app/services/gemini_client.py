"""
Kairos AI — Gemini Client
Wrapper for Google Generative AI using the new google.genai SDK.
Uses gemini-2.0-flash model.
"""
import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_client():
    """Get the Gemini client (singleton)."""
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment variables.")

    _client = genai.Client(api_key=api_key)
    return _client


async def gemini_json_call(system_prompt: str, user_prompt: str) -> dict:
    """
    Call Gemini with a system + user prompt and parse JSON response.
    Returns parsed dict. Handles markdown code fences in response.
    """
    client = get_client()

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=f"System: {system_prompt}\n\nUser: {user_prompt}",
        config=types.GenerateContentConfig(
            temperature=0.3,
            response_mime_type="application/json"
        )
    )

    text = response.text.strip()

    # Clean markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    return json.loads(text)


async def gemini_text_call(system_prompt: str, user_prompt: str) -> str:
    """
    Call Gemini with a system + user prompt and return raw text.
    """
    client = get_client()

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=f"System: {system_prompt}\n\nUser: {user_prompt}",
        config=types.GenerateContentConfig(temperature=0.3)
    )

    return response.text.strip()
