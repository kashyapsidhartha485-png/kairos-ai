"""
Kairos AI — Smoke Test Script
Verifies all environment variables and service connections.

Run: python -m scripts.smoke_test
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def check_env_vars():
    """Check all required environment variables."""
    print("📋 Checking environment variables...")
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

    all_ok = True
    for var in required:
        value = os.getenv(var)
        if value and not value.startswith("your_"):
            print(f"  ✅ {var}: {'*' * min(len(value), 8)}...")
        else:
            print(f"  ❌ {var}: NOT SET or placeholder")
            all_ok = False

    return all_ok


def check_firebase():
    """Test Firebase connection."""
    print("\n🔥 Testing Firebase connection...")
    try:
        from app.services.firebase_client import get_db
        db = get_db()
        # Try a simple read
        collections = [c.id for c in db.collections()]
        print(f"  ✅ Firebase connected. Collections: {collections}")
        return True
    except Exception as e:
        print(f"  ❌ Firebase error: {e}")
        return False


def check_gemini():
    """Test Gemini API."""
    print("\n🤖 Testing Gemini API...")
    try:
        from app.services.gemini_client import get_model
        model = get_model()
        response = model.generate_content("Say hello in one word.")
        print(f"  ✅ Gemini response: {response.text.strip()}")
        return True
    except Exception as e:
        print(f"  ❌ Gemini error: {e}")
        return False


def check_deepface():
    """Test DeepFace installation."""
    print("\n🧠 Testing DeepFace...")
    try:
        from deepface import DeepFace
        print("  ✅ DeepFace imported successfully")
        print("  ℹ️  Model will be downloaded on first use (~390MB)")
        return True
    except Exception as e:
        print(f"  ❌ DeepFace error: {e}")
        return False


def main():
    print("=" * 60)
    print("  KAIROS AI — Smoke Test")
    print("=" * 60)

    results = {
        "Environment Variables": check_env_vars(),
        "Firebase": check_firebase(),
        "Gemini AI": check_gemini(),
        "DeepFace": check_deepface()
    }

    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    for name, ok in results.items():
        emoji = "✅" if ok else "❌"
        print(f"  {emoji} {name}")

    all_passed = all(results.values())
    print()
    if all_passed:
        print("  🎉 All checks passed! Ready for development.")
    else:
        print("  ⚠️  Some checks failed. Fix the issues above before proceeding.")
    print("=" * 60)


if __name__ == "__main__":
    main()
