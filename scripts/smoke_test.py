"""
Kairos AI — Smoke Test Script
Verifies all environment variables and service connections.

Run: py -m scripts.smoke_test
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def check_env_vars():
    """Check all required environment variables."""
    print("Checking environment variables...")
    required = [
        "FIREBASE_CREDENTIALS_PATH",
        "GEMINI_API_KEY",
        "GOOGLE_MAPS_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_PHONE_NUMBER",
        "TELEGRAM_BOT_TOKEN",
        "BACKEND_BASE_URL"
    ]

    # Categorize: critical vs optional
    critical = ["FIREBASE_CREDENTIALS_PATH", "GEMINI_API_KEY", "BACKEND_BASE_URL"]
    all_critical_ok = True

    for var in required:
        value = os.getenv(var)
        is_crit = var in critical
        tag = "[CRITICAL]" if is_crit else "[OPTIONAL]"
        if value and not value.startswith("your_"):
            print(f"  OK {tag} {var}: {'*' * min(len(value), 8)}...")
        else:
            print(f"  MISSING {tag} {var}: NOT SET or placeholder")
            if is_crit:
                all_critical_ok = False

    return all_critical_ok


def check_firebase():
    """Test Firebase connection."""
    print("\nTesting Firebase connection...")
    try:
        from app.services.firebase_client import get_db
        db = get_db()
        # Try a simple read
        collections = [c.id for c in db.collections()]
        print(f"  OK Firebase connected. Collections: {collections}")
        return True
    except Exception as e:
        print(f"  FAIL Firebase error: {e}")
        return False


def check_gemini():
    """Test Gemini API."""
    print("\nTesting Gemini API...")
    try:
        from app.services.gemini_client import get_client
        client = get_client()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents="Say hello in one word."
        )
        print(f"  OK Gemini response: {response.text.strip()}")
        return True
    except Exception as e:
        print(f"  FAIL Gemini error: {e}")
        return False


def check_adk():
    """Test Google ADK imports."""
    print("\nTesting Google ADK...")
    try:
        from google.adk.agents import LlmAgent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
        print("  OK Google ADK imported successfully")
        return True
    except Exception as e:
        print(f"  FAIL ADK error: {e}")
        return False


def check_deepface():
    """Test DeepFace installation."""
    print("\nTesting DeepFace...")
    try:
        from deepface import DeepFace
        print("  OK DeepFace imported successfully")
        print("  INFO Model will be downloaded on first use (~390MB)")
        return True
    except Exception as e:
        print(f"  FAIL DeepFace error: {e}")
        return False


def check_app_import():
    """Test that the FastAPI app can be imported."""
    print("\nTesting FastAPI app import...")
    try:
        from app.main import app
        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        print(f"  OK App imported. Routes: {len(routes)} endpoints")
        # List key routes
        key_prefixes = ["/api/register", "/api/emergency", "/api/driver", "/api/hospital", "/api/ambulance"]
        for prefix in key_prefixes:
            count = len([r for r in routes if r.startswith(prefix)])
            print(f"    {prefix}: {count} endpoints")
        return True
    except Exception as e:
        print(f"  FAIL App import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("  KAIROS AI - Smoke Test")
    print("=" * 60)

    results = {
        "Environment Variables": check_env_vars(),
        "Firebase": check_firebase(),
        "Gemini AI": check_gemini(),
        "Google ADK": check_adk(),
        "DeepFace": check_deepface(),
        "FastAPI App": check_app_import(),
    }

    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")

    all_passed = all(results.values())
    print()
    if all_passed:
        print("  All checks passed! Ready for development.")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"  {len(failed)} check(s) failed: {', '.join(failed)}")
        print("  Fix the issues above before proceeding.")
    print("=" * 60)


if __name__ == "__main__":
    main()
