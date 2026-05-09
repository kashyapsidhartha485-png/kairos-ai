"""
Kairos AI — Reset Demo State
Cleans up stale emergencies and resets ambulances for a fresh demo.
Run: python -m scripts.reset_demo
"""
from app.services.firebase_client import emergencies_ref, ambulances_ref, driver_notifications_ref

def reset():
    print("=" * 50)
    print("  KAIROS AI — Resetting Demo State")
    print("=" * 50)

    # Close all active emergencies
    count = 0
    for doc in emergencies_ref().stream():
        e = doc.to_dict()
        if e.get("status") in ["active", "routed", "bed_confirmed"]:
            emergencies_ref().document(doc.id).update({"status": "cancelled"})
            count += 1
            print(f"  ❌ Closed emergency: {doc.id}")
    print(f"  Closed {count} stale emergencies\n")

    # Reset all ambulances to available
    for doc in ambulances_ref().stream():
        ambulances_ref().document(doc.id).update({
            "status": "available",
            "heading": "idle",
            "progress_percent": 0
        })
        print(f"  ✅ {doc.id} → available")
    print()

    # Clear old driver notifications
    notif_count = 0
    for doc in driver_notifications_ref().stream():
        driver_notifications_ref().document(doc.id).delete()
        notif_count += 1
    print(f"  🗑️  Cleared {notif_count} old notifications\n")

    print("=" * 50)
    print("  ✅ Demo state reset! Ready for a fresh run.")
    print("=" * 50)

if __name__ == "__main__":
    reset()
