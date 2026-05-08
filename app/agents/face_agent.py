"""
Kairos AI — Face Agent
Uses DeepFace (ArcFace + RetinaFace) for face embedding 
generation and matching against registered users.
PRD Sections 6.1, 9.2, 9.3, 9.4, 9.5

NOTE: DeepFace/TensorFlow are loaded lazily to avoid protobuf
version conflicts at import time. The models are loaded on first use.
"""
import numpy as np
import os
import time
import traceback
from app.services.firebase_client import users_ref


def _get_deepface():
    """Lazy-load DeepFace to avoid protobuf conflicts at import time."""
    try:
        from deepface import DeepFace
        return DeepFace
    except Exception as e:
        raise ImportError(
            f"DeepFace could not be loaded (likely protobuf version conflict): {e}. "
            "Face recognition is unavailable. Install compatible protobuf version."
        )


def generate_embedding(img_path: str) -> list:
    """
    Generate a 512-dimensional face embedding from an image.
    
    Args:
        img_path: Path to the image file
        
    Returns:
        List of 512 floats (ArcFace embedding)
        
    Raises:
        ValueError: If no face detected in the image
    """
    DeepFace = _get_deepface()
    try:
        result = DeepFace.represent(
            img_path=img_path,
            model_name="ArcFace",
            detector_backend="retinaface"
        )
        if not result or len(result) == 0:
            raise ValueError("No face detected in the image.")
        return result[0]["embedding"]
    except Exception as e:
        if "Face could not be detected" in str(e) or "No face" in str(e):
            raise ValueError(f"Face not detected: {str(e)}")
        raise


def compute_l2_distance(emb1: list, emb2: list) -> float:
    """Compute L2 (Euclidean) distance between two embeddings."""
    return float(np.linalg.norm(np.array(emb1) - np.array(emb2)))


async def match(img_path: str) -> dict:
    """
    Match a victim's face photo against all registered users.
    
    Args:
        img_path: Path to the victim's photo
        
    Returns:
        dict with keys:
            - identification_status: "identified" | "not_identified"
            - confidence: "high" | "medium" | None
            - patient_id: str | None
            - patient_data: dict | None
            - distance: float | None
            - time_taken_ms: int
    """
    start_time = time.time()

    try:
        # Step 1: Generate embedding from victim photo
        victim_embedding = generate_embedding(img_path)

        # Step 2: Fetch all registered users with embeddings
        users_docs = users_ref().stream()

        best_match = None
        best_distance = float('inf')
        best_user_data = None
        best_user_id = None

        for doc in users_docs:
            user_data = doc.to_dict()
            user_embeddings = user_data.get("embedding", [])

            if not user_embeddings:
                continue

            # Step 3: Compute min L2 distance across user's multiple embeddings
            for stored_emb in user_embeddings:
                distance = compute_l2_distance(victim_embedding, stored_emb)
                if distance < best_distance:
                    best_distance = distance
                    best_user_id = doc.id
                    best_user_data = user_data

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Step 4: Threshold logic
        if best_distance < 12.0:
            return {
                "identification_status": "identified",
                "confidence": "high",
                "patient_id": best_user_id,
                "patient_data": best_user_data,
                "distance": best_distance,
                "time_taken_ms": elapsed_ms
            }
        elif best_distance < 15.0:
            return {
                "identification_status": "identified",
                "confidence": "medium",
                "patient_id": best_user_id,
                "patient_data": best_user_data,
                "distance": best_distance,
                "time_taken_ms": elapsed_ms,
                "warning": "Medium confidence match -- verify patient identity"
            }
        else:
            return {
                "identification_status": "not_identified",
                "confidence": None,
                "patient_id": None,
                "patient_data": None,
                "distance": best_distance if best_distance != float('inf') else None,
                "time_taken_ms": elapsed_ms
            }

    except ValueError as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        raise
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        print(f"[Face Agent] Error during matching: {e}")
        traceback.print_exc()
        raise
