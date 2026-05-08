"""
Kairos AI — Firebase Client
Initializes Firebase Admin SDK and provides Firestore DB access.
"""
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

_app = None
_db = None


def get_firebase_app():
    """Initialize and return the Firebase Admin app (singleton)."""
    global _app
    if _app is not None:
        return _app

    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json")

    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
    else:
        # Fallback: try loading from environment variable as JSON string
        cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
        if cred_json:
            cred_data = json.loads(cred_json)
            cred = credentials.Certificate(cred_data)
        else:
            raise FileNotFoundError(
                f"Firebase credentials not found at '{cred_path}' "
                "and FIREBASE_CREDENTIALS_JSON env var is not set. "
                "Download your service account key from Firebase Console → "
                "Project Settings → Service Accounts → Generate New Private Key."
            )

    _app = firebase_admin.initialize_app(cred)
    return _app


def get_db() -> firestore.firestore.Client:
    """Get the Firestore database client (singleton)."""
    global _db
    if _db is not None:
        return _db

    get_firebase_app()
    _db = firestore.client()
    return _db


# ──────────────────────────────────────────────
# Collection References (convenience)
# ──────────────────────────────────────────────

def users_ref():
    return get_db().collection("users")


def emergencies_ref():
    return get_db().collection("emergencies")


def ambulances_ref():
    return get_db().collection("ambulances")


def hospitals_ref():
    return get_db().collection("hospitals")


def patient_conditions_ref():
    return get_db().collection("patient_conditions")


def hospital_verifications_ref():
    return get_db().collection("hospital_verifications")


def emergency_events_ref():
    return get_db().collection("emergency_events")


def driver_notifications_ref():
    return get_db().collection("driver_notifications")
