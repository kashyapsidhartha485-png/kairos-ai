"""
Kairos AI — Pydantic Models (Schemas)
All request/response models for the API.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
import uuid


# ──────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────

class RegisterResponse(BaseModel):
    user_id: str
    qr_code_base64: str
    message: str = "Registration successful"


# ──────────────────────────────────────────────
# Emergency — Identification
# ──────────────────────────────────────────────

class PatientCard(BaseModel):
    name: str
    age: int
    blood_group: str
    conditions: Optional[str] = None
    allergies: Optional[str] = None
    medications: Optional[str] = None
    emergency_contact_name: str
    emergency_contact_phone: str


class FirstAidGuidance(BaseModel):
    dos: List[str]
    donts: List[str]
    cpr_needed: bool


class IdentifyResponse(BaseModel):
    emergency_id: str
    identification_status: str  # "identified" | "not_identified"
    confidence: Optional[str] = None  # "high" | "medium" | null
    patient: Optional[PatientCard] = None
    first_aid_guidance: Optional[FirstAidGuidance] = None
    warning: Optional[str] = None


class DuplicateCheckResponse(BaseModel):
    duplicate: bool
    existing_emergency_id: Optional[str] = None


# ──────────────────────────────────────────────
# Emergency — Manual Info
# ──────────────────────────────────────────────

class ManualInfoRequest(BaseModel):
    approximate_age: Optional[int] = None
    gender: Optional[str] = None
    visible_injuries: Optional[str] = None
    known_conditions: Optional[str] = None


class ManualInfoResponse(BaseModel):
    success: bool


# ──────────────────────────────────────────────
# Emergency — Condition (Companion Input)
# ──────────────────────────────────────────────

class ConditionRequest(BaseModel):
    symptoms: str
    vitals: Optional[str] = None
    consciousness_level: Optional[str] = None
    visible_injuries: Optional[str] = None


class ConditionResponse(BaseModel):
    success: bool
    message: str = "Condition received. AI routing in progress."


# ──────────────────────────────────────────────
# Triage
# ──────────────────────────────────────────────

class TriageResult(BaseModel):
    condition_summary: str
    emergency_type: str  # cardiac/trauma/neurological/respiratory/other
    bed_type_needed: str  # ICU/general/trauma/ventilator
    specialist_needed: Optional[str] = None
    urgency: str  # critical/high/medium
    additional_notes: Optional[str] = None


# ──────────────────────────────────────────────
# Ambulance — Dispatch
# ──────────────────────────────────────────────

class AmbulanceInfo(BaseModel):
    id: str
    driver_name: str
    current_lat: float
    current_lng: float
    eta_minutes: float


class DispatchResponse(BaseModel):
    assigned_ambulance: AmbulanceInfo
    prep_instructions: List[str]


class LocationUpdateRequest(BaseModel):
    ambulance_id: str
    lat: float
    lng: float


class LocationUpdateResponse(BaseModel):
    success: bool


class AmbulanceLocationResponse(BaseModel):
    lat: float
    lng: float
    eta_minutes: float


# ──────────────────────────────────────────────
# Driver
# ──────────────────────────────────────────────

class DriverStatusResponse(BaseModel):
    status: str
    emergency_id: Optional[str] = None
    patient: Optional[PatientCard] = None
    prep_instructions: Optional[List[str]] = None
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    routing_status: Optional[str] = None
    chosen_hospital: Optional[dict] = None


# ──────────────────────────────────────────────
# Hospital
# ──────────────────────────────────────────────

class HospitalEmergencyView(BaseModel):
    id: str
    patient: Optional[PatientCard] = None
    unidentified_notes: Optional[str] = None
    triage_result: Optional[dict] = None
    live_condition: Optional[dict] = None
    ambulance_eta_minutes: Optional[float] = None
    ambulance_status: Optional[str] = None
    scoring_reason: Optional[str] = None


class HospitalStatusResponse(BaseModel):
    emergency: Optional[HospitalEmergencyView] = None
    new_patient_alert: bool = False


class ConfirmBedRequest(BaseModel):
    emergency_id: str
    status: str  # "confirmed" | "unavailable"


class ConfirmBedResponse(BaseModel):
    success: bool = True
    re_routing: bool = False
    message: Optional[str] = None


class AcknowledgeResponse(BaseModel):
    success: bool


# ──────────────────────────────────────────────
# Routing Status (Polling)
# ──────────────────────────────────────────────

class HospitalCheckStatus(BaseModel):
    name: str
    status: str
    method: Optional[str] = None


class RoutingStatusResponse(BaseModel):
    routing_status: str = "pending"  # checking_hospitals | calling_{hospital} | hospital_confirmed | routing_complete
    hospitals_checked: List[HospitalCheckStatus] = []
    chosen_hospital: Optional[dict] = None


# ──────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
