"""
Kairos AI — Registration Router
POST /api/register — User registration with face embedding pipeline.
PRD Sections 6.1, 9.2, 9.3
"""
import os
import io
import base64
import uuid
import tempfile
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List

from app.agents.face_agent import generate_embedding
from app.services.firebase_client import users_ref, emergency_events_ref
from app.models.schemas import RegisterResponse

import qrcode

router = APIRouter(prefix="/api", tags=["Registration"])


@router.post("/register", response_model=RegisterResponse)
async def register_user(
    name: str = Form(...),
    age: int = Form(...),
    blood_group: str = Form(...),
    conditions: str = Form(None),
    allergies: str = Form(None),
    medications: str = Form(None),
    emergency_contact_name: str = Form(...),
    emergency_contact_phone: str = Form(...),
    photos: List[UploadFile] = File(...)
):
    """
    Register a new user with face embeddings.
    
    Accepts 3-5 photos, generates ArcFace embeddings for each,
    stores all embeddings in Firestore, and returns a QR code.
    Raw photos are NEVER persisted (PRD Section 9.3).
    """
    # Validate photo count
    if len(photos) < 3:
        raise HTTPException(
            status_code=400,
            detail="At least 3 photos are required for registration. "
                   "Please upload 3-5 clear front-facing photos."
        )
    if len(photos) > 5:
        raise HTTPException(
            status_code=400,
            detail="Maximum 5 photos allowed for registration."
        )

    embeddings = []
    temp_files = []

    try:
        for i, photo in enumerate(photos):
            # Save temporarily
            suffix = os.path.splitext(photo.filename or "photo.jpg")[1] or ".jpg"
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp_file.write(await photo.read())
            tmp_file.close()
            temp_files.append(tmp_file.name)

            # Generate embedding
            try:
                embedding = generate_embedding(tmp_file.name)
                embeddings.append(embedding)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Face not detected in photo {i + 1}. "
                           "Please re-upload a clear front-facing photo."
                )

    finally:
        # Delete ALL temp files immediately (photos never persisted)
        for tmp_path in temp_files:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # Generate user ID
    user_id = str(uuid.uuid4())

    # Store user in Firestore
    user_data = {
        "name": name,
        "age": age,
        "blood_group": blood_group,
        "conditions": conditions,
        "allergies": allergies,
        "medications": medications,
        "emergency_contact_name": emergency_contact_name,
        "emergency_contact_phone": emergency_contact_phone,
        "embedding": embeddings,  # Array of arrays
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    users_ref().document(user_id).set(user_data)

    # Generate QR code
    backend_url = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
    deep_link = f"{backend_url}/emergency?hint={name}"

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(deep_link)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    qr_img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # Log registration event
    emergency_events_ref().add({
        "emergency_id": None,
        "event_type": "user_registered",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "user_id": user_id,
            "name": name,
            "photos_processed": len(embeddings)
        }
    })

    return RegisterResponse(
        user_id=user_id,
        qr_code_base64=qr_base64,
        message="Registration successful"
    )
