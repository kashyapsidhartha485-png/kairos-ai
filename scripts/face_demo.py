"""
Kairos AI - Face Verification Demo
===================================
This script lets you test face recognition yourself!

HOW TO USE:
-----------
1. Take 3+ selfie photos and save them somewhere (e.g. Desktop)
2. Run: py scripts/face_demo.py register <photo1> <photo2> <photo3>
3. Take a NEW photo (different angle/lighting)
4. Run: py scripts/face_demo.py identify <new_photo>
5. It should match you!

QUICK TEST (using webcam):
--------------------------
py scripts/face_demo.py webcam-register    # Takes 3 photos via webcam
py scripts/face_demo.py webcam-identify    # Takes 1 photo and tries to match
"""
import sys
import os
import uuid
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

BASE = "http://localhost:8000"


def capture_webcam_photos(count=3, delay=2):
    """Capture photos from webcam using OpenCV."""
    try:
        import cv2
    except ImportError:
        print("OpenCV not installed. Installing...")
        os.system("py -m pip install opencv-python")
        import cv2

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open webcam!")
        return []

    photos = []
    save_dir = os.path.join(os.path.dirname(__file__), "demo_photos")
    os.makedirs(save_dir, exist_ok=True)

    print(f"\n  Webcam ready! Will capture {count} photos.")
    print(f"  Press SPACE to capture, ESC to cancel.\n")

    captured = 0
    while captured < count:
        ret, frame = cap.read()
        if not ret:
            break

        # Show preview with overlay
        display = frame.copy()
        cv2.putText(display, f"Photo {captured + 1}/{count} - Press SPACE to capture",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Kairos AI - Face Capture", display)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            print("  Cancelled.")
            break
        elif key == 32:  # SPACE
            filename = os.path.join(save_dir, f"capture_{captured + 1}.jpg")
            cv2.imwrite(filename, frame)
            photos.append(filename)
            captured += 1
            print(f"  Captured photo {captured}/{count}: {filename}")
            time.sleep(0.5)

    cap.release()
    cv2.destroyAllWindows()
    return photos


def register_with_photos(photo_paths):
    """Register a user with face photos via the API."""
    import requests

    print("\n" + "=" * 60)
    print("  FACE REGISTRATION")
    print("=" * 60)

    # Validate photos exist
    for p in photo_paths:
        if not os.path.exists(p):
            print(f"  ERROR: File not found: {p}")
            return

    print(f"  Photos: {len(photo_paths)}")
    for p in photo_paths:
        size_kb = os.path.getsize(p) / 1024
        print(f"    - {os.path.basename(p)} ({size_kb:.0f} KB)")

    # Prepare multipart upload
    files = []
    for p in photo_paths:
        files.append(("photos", (os.path.basename(p), open(p, "rb"), "image/jpeg")))

    data = {
        "name": "Sidhartha",
        "age": 22,
        "blood_group": "O+",
        "conditions": "None",
        "allergies": "None",
        "medications": "None",
        "emergency_contact_name": "Emergency Contact",
        "emergency_contact_phone": "+919876543210"
    }

    print(f"\n  Registering as: {data['name']}")
    print("  Uploading photos and generating face embeddings...")
    print("  (This may take 30-60 seconds on first run - downloading AI model)")

    r = requests.post(f"{BASE}/api/register", data=data, files=files)

    # Close file handles
    for _, (_, fh, _) in files:
        fh.close()

    if r.status_code == 200:
        result = r.json()
        print(f"\n  SUCCESS!")
        print(f"  Patient ID: {result.get('patient_id', 'N/A')}")
        print(f"  QR Code: {result.get('qr_code_url', 'N/A')}")
        print(f"  Embeddings: {result.get('embeddings_stored', 'N/A')} stored")

        # Save patient ID for later
        id_file = os.path.join(os.path.dirname(__file__), "demo_patient_id.txt")
        with open(id_file, "w") as f:
            f.write(result.get("patient_id", ""))
        print(f"\n  Patient ID saved to: {id_file}")
    else:
        print(f"\n  FAILED: {r.status_code}")
        print(f"  Response: {r.text[:500]}")


def identify_with_photo(photo_path):
    """Try to identify a person from a single photo."""
    import requests
    import random

    print("\n" + "=" * 60)
    print("  FACE IDENTIFICATION")
    print("=" * 60)

    if not os.path.exists(photo_path):
        print(f"  ERROR: File not found: {photo_path}")
        return

    size_kb = os.path.getsize(photo_path) / 1024
    print(f"  Photo: {os.path.basename(photo_path)} ({size_kb:.0f} KB)")
    print("  Searching for match in registered users...")

    files = {"photo": (os.path.basename(photo_path), open(photo_path, "rb"), "image/jpeg")}
    # Use slightly random coords each time to avoid duplicate emergency detection
    data = {
        "lat": 12.9716 + random.uniform(0.01, 0.05),
        "lng": 77.5946 + random.uniform(0.01, 0.05)
    }

    r = requests.post(f"{BASE}/api/emergency/identify", data=data, files=files)
    files["photo"][1].close()

    if r.status_code == 200:
        result = r.json()
        status = result.get("identification_status", "unknown")

        if status == "identified":
            print(f"\n  MATCH FOUND!")
            print(f"  Patient: {result.get('patient_name', 'N/A')}")
            print(f"  Blood Group: {result.get('blood_group', 'N/A')}")
            print(f"  Conditions: {result.get('conditions', 'N/A')}")
            print(f"  Confidence: {result.get('confidence', 'N/A')}")
            print(f"  Distance: {result.get('distance', 'N/A')}")
            print(f"  Time: {result.get('time_taken_ms', 'N/A')}ms")
            print(f"  Emergency ID: {result.get('emergency_id', 'N/A')}")
        elif status == "already_reported":
            print(f"\n  ALREADY REPORTED!")
            print(f"  This patient already has an active emergency.")
            print(f"  Warning: {result.get('warning', 'N/A')}")
            print(f"  Existing Emergency ID: {result.get('emergency_id', 'N/A')}")
            card = result.get("patient_card")
            if card:
                print(f"  Patient: {card.get('name', 'N/A')}")
                print(f"  Blood Group: {card.get('blood_group', 'N/A')}")
        elif status == "duplicate":
            print(f"\n  DUPLICATE EMERGENCY detected at this location.")
            print(f"  Emergency ID: {result.get('emergency_id', 'N/A')}")
            print(f"  (This means a recent emergency already exists nearby)")
        elif status == "not_identified":
            print(f"\n  NO MATCH - Patient not recognized")
            print(f"  Emergency ID: {result.get('emergency_id', 'N/A')}")
            print(f"  (An unidentified emergency was still created)")
        else:
            print(f"\n  Status: {status}")
            print(f"  Full response: {json.dumps(result, indent=2)[:500]}")
    else:
        print(f"\n  Error: {r.status_code}")
        print(f"  Response: {r.text[:500]}")


def webcam_register():
    """Register using webcam photos."""
    print("\n" + "=" * 60)
    print("  WEBCAM REGISTRATION MODE")
    print("=" * 60)
    print("  Will take 3 photos of your face.")
    print("  Look at the camera and press SPACE for each shot.")

    photos = capture_webcam_photos(count=3)
    if len(photos) >= 3:
        register_with_photos(photos)
    else:
        print(f"  Need at least 3 photos, got {len(photos)}")


def webcam_identify():
    """Identify using a webcam photo."""
    print("\n" + "=" * 60)
    print("  WEBCAM IDENTIFICATION MODE")
    print("=" * 60)
    print("  Will take 1 photo and try to match you.")

    photos = capture_webcam_photos(count=1)
    if photos:
        identify_with_photo(photos[0])
    else:
        print("  No photo captured.")


def main():
    print("=" * 60)
    print("  KAIROS AI - Face Verification Demo")
    print("=" * 60)

    if len(sys.argv) < 2:
        print("""
  Usage:
    py scripts/face_demo.py webcam-register     Take 3 webcam selfies to register
    py scripts/face_demo.py webcam-identify     Take 1 webcam photo to identify

    py scripts/face_demo.py register <p1> <p2> <p3>   Register with photo files
    py scripts/face_demo.py identify <photo>           Identify from photo file
        """)
        return

    command = sys.argv[1].lower()

    if command == "webcam-register":
        webcam_register()
    elif command == "webcam-identify":
        webcam_identify()
    elif command == "register":
        if len(sys.argv) < 5:
            print("  Need at least 3 photo paths!")
            print("  py scripts/face_demo.py register photo1.jpg photo2.jpg photo3.jpg")
            return
        register_with_photos(sys.argv[2:])
    elif command == "identify":
        if len(sys.argv) < 3:
            print("  Need a photo path!")
            print("  py scripts/face_demo.py identify photo.jpg")
            return
        identify_with_photo(sys.argv[2])
    else:
        print(f"  Unknown command: {command}")


if __name__ == "__main__":
    main()
