# Kairos AI — Full Workflow Walkthrough

## Scenario: Ram meets with an accident

Ram (22, registered in the app with face data, blood group B+, known asthmatic) collapses on MG Road, Bangalore after a bike accident. A bystander opens the Kairos app.

---

## 🧑 Phase 1: Bystander Perspective

### Step 1 — Face Scan
Bystander opens camera → snaps Ram's photo → hits **"Report Emergency"**

**API:** `POST /api/emergency/identify`
```json
{
  "image": "<base64 photo>",
  "bystander_lat": 12.9750,
  "bystander_lng": 77.6060,
  "bystander_notes": "Bike accident, bleeding from leg, conscious"
}
```

**What happens inside:**
```
Photo → DeepFace → matches Ram's registered embedding
      → Returns Ram's full medical profile from Firestore
```

**Response bystander sees:**
```json
{
  "status": "identified",
  "patient_name": "Ram",
  "emergency_id": "EMR-20260509-001",
  "message": "Patient identified. Emergency created. Ambulance dispatched."
}
```

> If Ram was already reported in the last 10 minutes → returns `"already_reported"` (dedup)

### Step 2 — Triage (automatic, no bystander input needed)
The **Triage Agent** (Gemini 2.5 Flash) runs automatically:

```
Input: bystander_notes + Ram's medical history (asthma, allergies)
   ↓
Gemini analyzes → generates triage result
```

**Triage output stored in Firestore:**
```json
{
  "emergency_type": "trauma",
  "severity": "high",
  "bed_type_needed": "ICU",
  "specialist_needed": "orthopedic surgeon",
  "urgency": "critical",
  "symptoms": ["open wound on leg", "possible fracture", "conscious"],
  "vitals": {},
  "prep_instructions": [
    "Apply tourniquet above wound",
    "Immobilize the leg",
    "Check for spinal injury before moving",
    "Administer bronchodilator if breathing difficulty (known asthmatic)"
  ]
}
```

### Step 3 — First Aid (shown to bystander)
The **First Aid Agent** generates instructions displayed on the bystander's screen:
- "Apply pressure to the wound with clean cloth"
- "Do NOT move the patient's leg"
- "Keep him talking, monitor consciousness"

### Step 4 — Bystander waits
Bystander sees: **"Ambulance AMB-001 dispatched. ETA: 8 minutes"**

---

## 🚑 Phase 2: Ambulance Driver Perspective

### Step 5 — Driver gets alert
The closest available ambulance (AMB-001, driver Rajesh Kumar) is assigned.

**API (Prince's frontend polls this):** `GET /api/driver/AMB-001/dashboard`

**Driver sees:**
```json
{
  "status": "dispatched",
  "emergency_id": "EMR-20260509-001",
  "patient": {
    "name": "Ram",
    "age": 22,
    "blood_group": "B+",
    "conditions": "Asthma",
    "allergies": "Penicillin",
    "emergency_contact_name": "Sita (Mother)",
    "emergency_contact_phone": "+91..."
  },
  "pickup_lat": 12.9750,
  "pickup_lng": 77.6060,
  "pickup_directions_link": "https://www.google.com/maps/dir/?api=1&origin=12.98,77.60&destination=12.975,77.606&travelmode=driving",
  "prep_instructions": [
    "Apply tourniquet above wound",
    "Immobilize the leg",
    "Administer bronchodilator if needed (asthmatic)"
  ]
}
```

Driver clicks the **Google Maps link** → gets turn-by-turn navigation to Ram.

### Step 6 — Ambulance moves (SIMULATION)
**This is where `simulation.py` kicks in.**

**API:** `POST /api/simulation/start?emergency_id=EMR-20260509-001&ambulance_id=AMB-001&speed=2`

**What happens:**
```
Phase 1: Ambulance GPS moves from (12.98, 77.60) → (12.975, 77.606) [to patient]
  → Firestore updated every ~0.8 seconds with new lat/lng
  → Prince's frontend polls GET /api/simulation/status/EMR-20260509-001
  → Shows ambulance dot moving on Google Maps

Phase 2: Patient picked up
  → Status changes to "patient_picked_up"
  → 2 second pause

Phase 3: Ambulance GPS moves from patient → hospital
  → Same Firestore updates
  → Frontend shows ambulance moving to hospital
```

**Prince's frontend polls every 1 second:**
```
GET /api/simulation/status/EMR-20260509-001

Response:
{
  "phase": "en_route_to_hospital",
  "status_text": "En route to Apollo Hospital (65%)",
  "progress_percent": 82,
  "ambulance": { "lat": 12.935, "lng": 77.598, "heading": "to_hospital" },
  "patient": { "lat": 12.975, "lng": 77.606 },
  "hospital": { "lat": 12.8917, "lng": 77.5963, "name": "Apollo Hospital" }
}
```

### Step 7 — Meanwhile: Hospital routing runs in parallel

While the ambulance is moving, the **Orchestrator Agent** autonomously:

```
1. get_triage_result()     → "needs ICU + orthopedic surgeon"
2. get_nearby_hospitals()  → finds Apollo, Manipal, Fortis
3. check_hospital_beds()   → Apollo: FRESH data, 0 ICU beds ❌
4. check_hospital_beds()   → Manipal: STALE data → triggers VOICE CALL ☎️
5. check_hospital_beds()   → Fortis: STALE data → triggers VOICE CALL ☎️
```

### Step 8 — Voice calls happen (parallel)

**Two phones ring simultaneously:**

**Manipal call (Friend A: 7257959463):**
> *"This is Kairos Emergency AI dispatch. We have a 22-year-old male presenting with suspected open fracture of the right tibia following a motor vehicle collision. Patient has a known history of bronchial asthma. Requires ICU admission with orthopedic surgical consultation. Does your facility have ICU availability? Please say Yes or No."*

**Fortis call (Friend B: 7970866804):**
> Same script, different hospital name.

**Gemini generated this script** from Ram's actual triage data. Not hardcoded.

Friend A says "Yes" → Gemini parses → `bed_available: true`
Friend B says "No" → Gemini parses → `bed_available: false`

### Step 9 — Orchestrator decides

```
Apollo:  ❌ No ICU (digital check)
Manipal: ✅ ICU available, 12 min drive, has orthopedics
Fortis:  ❌ No ICU (voice call confirmed)

DECISION → Manipal Hospital
REASON: "ICU bed verified via voice call, orthopedic specialization matches,
         12-minute drive time is acceptable for critical trauma patient"
```

### Step 10 — Driver gets hospital navigation

Driver dashboard auto-updates:
```json
{
  "hospital_name": "Manipal Hospital",
  "hospital_address": "HAL Airport Road, Bangalore",
  "hospital_phone": "+917257959463",
  "hospital_directions_link": "https://www.google.com/maps/dir/?api=1&origin=12.975,77.606&destination=12.959,77.648&travelmode=driving",
  "scoring_reason": "ICU bed verified, orthopedic specialization, 12 min drive"
}
```

Driver clicks → Google Maps navigates to Manipal Hospital.

---

## 🏥 Phase 3: Hospital Receptionist Perspective

### Step 11 — Hospital gets alert

**API (Prince's frontend polls):** `GET /api/hospital/HOSP-MANIPAL/status`

```json
{
  "new_patient_alert": true,
  "emergency": {
    "id": "EMR-20260509-001",
    "patient": {
      "name": "Ram",
      "age": 22,
      "blood_group": "B+",
      "conditions": "Asthma",
      "allergies": "Penicillin",
      "emergency_contact_name": "Sita (Mother)"
    },
    "triage_result": {
      "emergency_type": "trauma",
      "bed_type_needed": "ICU",
      "specialist_needed": "orthopedic surgeon"
    },
    "ambulance_eta_minutes": 12.3,
    "scoring_reason": "ICU bed verified, orthopedic specialization"
  }
}
```

### Step 12 — Hospital acknowledges

Receptionist clicks **"Acknowledge"** on their dashboard:

`POST /api/hospital/HOSP-MANIPAL/acknowledge`

If they DON'T acknowledge within 2 minutes → automatic SMS sent to hospital phone.

### Step 13 — Hospital confirms bed

Receptionist clicks **"Confirm Bed"**:

`POST /api/hospital/HOSP-MANIPAL/confirm-bed`
```json
{ "emergency_id": "EMR-20260509-001", "status": "confirmed" }
```

**If they click "Unavailable"** → system automatically re-routes to the next hospital (Orchestrator re-runs excluding Manipal).

### Step 14 — Hospital tracks ambulance

`GET /api/hospital/HOSP-MANIPAL/ambulance-location`
```json
{
  "lat": 12.945,
  "lng": 77.625,
  "eta_minutes": 6.2
}
```

This updates in real-time as the simulation moves the ambulance.

### Step 15 — Patient delivered

Simulation reaches hospital → status becomes `"arrived"` → Driver marks complete:

`POST /api/driver/AMB-001/complete`

Emergency closed. Ambulance back to `"available"`.

---

## 🔄 Switching from Simulation to Real Ambulance

To switch to **real GPS tracking** instead of simulated movement:

### What to change:

| Component | Simulation (Now) | Production |
|---|---|---|
| **Ambulance GPS** | `simulation.py` updates Firestore | Mobile app sends GPS via `POST /api/ambulance/{id}/location` |
| **Movement** | Interpolated waypoints | Real phone GPS every 3-5 seconds |
| **Hospital phones** | Your friends' numbers | Actual hospital ER numbers |
| **Twilio** | Trial account (press-key prompt) | Paid account ($15.50, no prompt) |

### Steps to switch:

1. **Remove simulation dependency** — Prince's frontend stops calling `/api/simulation/start` and instead reads ambulance GPS from `GET /api/driver/{id}/dashboard` (which already reads real Firestore data)

2. **Add GPS update endpoint** — Already exists at:
   ```
   POST /api/ambulance/{id}/location
   Body: { "lat": 12.95, "lng": 77.63 }
   ```
   The driver's mobile app sends this every 5 seconds.

3. **Update hospital phones** — In `seed_data.py`, replace the demo numbers with real hospital ER desk numbers.

4. **Upgrade Twilio** — Pay $15.50, removes "press any key" prompt.

5. **That's it.** Everything else (triage, face recognition, voice calls, routing) works exactly the same. The simulation is just a GPS faker — swap it out and the rest of the pipeline doesn't care where the GPS comes from.
