"""
Kairos AI — Seed Mock Data Script
Inserts demo ambulances and hospitals into Firestore.
PRD Section 15.3

Run: python -m scripts.seed_data
"""
import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from app.services.firebase_client import ambulances_ref, hospitals_ref


def seed_ambulances():
    """Insert 3 demo ambulances."""
    ambulances = [
        {
            "driver_name": "Rajesh Kumar",
            "driver_phone": "+919876543210",
            "current_lat": 12.9716,
            "current_lng": 77.5946,
            "status": "available",
            "capability": "ALS",
            "telegram_chat_id": ""  # Fill with real Telegram chat ID
        },
        {
            "driver_name": "Anil Sharma",
            "driver_phone": "+919876543211",
            "current_lat": 12.9800,
            "current_lng": 77.6000,
            "status": "busy",
            "capability": "BLS",
            "telegram_chat_id": ""
        },
        {
            "driver_name": "Suresh Reddy",
            "driver_phone": "+919876543212",
            "current_lat": 12.9650,
            "current_lng": 77.5850,
            "status": "available",
            "capability": "BLS",
            "telegram_chat_id": ""
        }
    ]

    ids = ["AMB-001", "AMB-002", "AMB-003"]

    for amb_id, amb_data in zip(ids, ambulances):
        ambulances_ref().document(amb_id).set(amb_data)
        status_emoji = "✅" if amb_data["status"] == "available" else "🔴"
        print(f"  {status_emoji} {amb_id}: {amb_data['driver_name']} "
              f"({amb_data['capability']}, {amb_data['status']})")

    print(f"\n  📊 Inserted {len(ambulances)} ambulances")


def seed_hospitals():
    """Insert 3 demo hospitals."""
    now = datetime.now(timezone.utc)
    fresh = now.isoformat()
    stale = (now - timedelta(hours=2)).isoformat()  # 2 hours ago = stale

    hospitals = [
        {
            "name": "Apollo Hospital",
            "address": "Bannerghatta Road, Bangalore",
            "lat": 12.8917,
            "lng": 77.5963,
            "phone": "+911234567890",  # Replace with real number for demo
            "specializations": ["cardiology", "neurology", "trauma"],
            "icu_beds": 0,
            "general_beds": 5,
            "ventilator_beds": 2,
            "last_updated": fresh  # Fresh — digital check
        },
        {
            "name": "Manipal Hospital",
            "address": "HAL Airport Road, Bangalore",
            "lat": 12.9592,
            "lng": 77.6482,
            "phone": "+911234567891",  # Replace with Friend A's number
            "specializations": ["cardiology", "orthopedics"],
            "icu_beds": 1,
            "general_beds": 3,
            "ventilator_beds": 1,
            "last_updated": stale  # Stale — will trigger voice call
        },
        {
            "name": "Fortis Hospital",
            "address": "Cunningham Road, Bangalore",
            "lat": 12.9862,
            "lng": 77.5907,
            "phone": "+911234567892",  # Replace with Friend B's number
            "specializations": ["trauma", "general surgery"],
            "icu_beds": 1,
            "general_beds": 4,
            "ventilator_beds": 0,
            "last_updated": stale  # Stale — will trigger voice call
        }
    ]

    ids = ["HOSP-APOLLO", "HOSP-MANIPAL", "HOSP-FORTIS"]

    for hosp_id, hosp_data in zip(ids, hospitals):
        hospitals_ref().document(hosp_id).set(hosp_data)
        staleness = "🟢 FRESH" if hosp_data["last_updated"] == fresh else "🟡 STALE"
        print(f"  🏥 {hosp_id}: {hosp_data['name']} "
              f"(ICU: {hosp_data['icu_beds']}, {staleness})")

    print(f"\n  📊 Inserted {len(hospitals)} hospitals")


def main():
    print("=" * 60)
    print("  KAIROS AI — Seeding Mock Data to Firestore")
    print("=" * 60)
    print()

    print("🚑 Seeding Ambulances...")
    seed_ambulances()
    print()

    print("🏥 Seeding Hospitals...")
    seed_hospitals()
    print()

    print("=" * 60)
    print("  ✅ Seed data complete!")
    print("  📋 Verify in Firebase Console → Firestore Database")
    print("=" * 60)


if __name__ == "__main__":
    main()
