"""
Kairos AI — Gemini Client
Wrapper for Google Generative AI (Gemini 1.5 Flash).
"""
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

_model = None


def get_model():
    """Get the Gemini 1.5 Flash model (singleton)."""
    global _model
    if _model is not None:
        return _model

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment variables.")

    genai.configure(api_key=api_key)
    _model = genai.GenerativeModel("gemini-1.5-flash")
    return _model


async def gemini_json_call(system_prompt: str, user_prompt: str) -> dict:
    """
    Call Gemini with a system + user prompt and parse JSON response.
    Returns parsed dict. Handles markdown code fences in response.
    """
    model = get_model()

    response = model.generate_content(
        [
            {"role": "user", "parts": [f"System: {system_prompt}\n\nUser: {user_prompt}"]}
        ],
        generation_config=genai.GenerationConfig(
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
    model = get_model()

    response = model.generate_content(
        [
            {"role": "user", "parts": [f"System: {system_prompt}\n\nUser: {user_prompt}"]}
        ],
        generation_config=genai.GenerationConfig(temperature=0.3)
    )

    return response.text.strip()
