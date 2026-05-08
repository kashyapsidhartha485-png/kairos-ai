# 🚨 Kairos AI — Emergency Response in Under 90 Seconds

> **When someone collapses on the street, every second matters.**  
> Kairos AI replaces 15 minutes of frantic phone calls with a single photo.

---

## The Problem

In India, **30% of trauma deaths** happen because the ambulance went to the wrong hospital — one that had no ICU bed, no specialist, no ventilator. The patient gets bounced between hospitals while bleeding out.

**Current flow:** Bystander calls 108 → manual operator → calls hospitals one by one → 15+ minutes wasted.

## Our Solution

**Snap a photo. AI does everything else.**

```
📸 Photo → 🧠 Face ID → 🏥 AI calls hospitals → 🚑 Ambulance routed → 90 seconds
```

| What | How |
|------|-----|
| **Patient identified** | DeepFace matches face → pulls medical records, allergies, blood group |
| **Triage done** | Gemini 2.5 Flash analyzes condition → determines ICU/ventilator/specialist needed |
| **Hospitals verified** | AI **calls hospitals by phone** and asks "Do you have an ICU bed?" — in English, Hindi, or Kannada |
| **Best hospital picked** | Scores by: bed availability × drive time × specialist match |
| **Ambulance navigated** | Google Maps ETA → driver gets turn-by-turn to patient, then to hospital |
| **Hospital prepared** | ER gets patient card (name, blood group, allergies) before ambulance arrives |

---

## What Makes This Agentic?

No human decides anything. **Gemini 2.5 Flash is the brain:**

```
Orchestrator Agent THINKS:
  "Patient has a fracture. Needs ICU + orthopedic surgeon."
  
  → checks Apollo Hospital    → 0 ICU beds (digital check)
  → calls Manipal Hospital    → "Yes, ICU available" (voice call)
  → calls Fortis Hospital     → "No beds" (voice call)
  → calculates drive times    → Manipal: 12 min, Fortis: 18 min
  
  DECISION: Manipal Hospital
  REASON: "ICU verified, orthopedics available, shortest drive time"
```

**Nobody programmed this sequence.** The agent autonomously decides which hospitals to check, in what order, and picks the best one.

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Bystander   │────▶│   FastAPI     │────▶│  Gemini 2.5     │
│  (Photo)     │     │   Backend     │     │  Flash (ADK)    │
└─────────────┘     └──────┬───────┘     └────────┬────────┘
                           │                       │
              ┌────────────┼───────────────────────┤
              ▼            ▼                       ▼
        ┌──────────┐ ┌──────────┐          ┌─────────────┐
        │ DeepFace │ │ Firestore│          │  Twilio     │
        │ Face ID  │ │ Database │          │  Voice Call │
        └──────────┘ └──────────┘          └─────────────┘
              │            │                       │
              ▼            ▼                       ▼
        ┌──────────┐ ┌──────────────┐     ┌──────────────┐
        │ Patient  │ │ Google Maps  │     │  Hospital    │
        │ Records  │ │ ETA + Route  │     │  "Yes/No"    │
        └──────────┘ └──────────────┘     └──────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **AI Brain** | Google Gemini 2.5 Flash via ADK (Agent Development Kit) |
| **Face Recognition** | DeepFace (ArcFace model) |
| **Voice Calls** | Twilio + Gemini multimodal audio analysis |
| **Backend** | FastAPI (Python) |
| **Database** | Firebase Firestore (real-time) |
| **Maps & ETA** | Google Maps Distance Matrix API |
| **Languages** | English, Hindi, Kannada (voice + text) |

---

## 7 AI Agents Working Together

| # | Agent | What It Does |
|---|-------|-------------|
| 1 | **Triage Agent** | Analyzes symptoms → determines severity, bed type, specialist |
| 2 | **Face Agent** | Matches face → pulls patient medical history |
| 3 | **Orchestrator Agent** | The brain — autonomously checks hospitals and picks the best one |
| 4 | **Hospital Worker** | Checks bed counts (fresh data) or triggers voice call (stale data) |
| 5 | **Voice Agent** | Calls hospitals, speaks medical details, parses Yes/No response |
| 6 | **Scoring Agent** | Ranks hospitals by bed + distance + specialist match |
| 7 | **Closer Agent** | Finalizes routing, notifies driver, alerts hospital ER, SMSes family |

---

## Live Demo Flow

```
Step 1:  Bystander snaps photo of "patient"
Step 2:  System identifies patient from face database (< 2 sec)
Step 3:  AI triages: "Trauma, needs ICU + orthopedic surgeon"
Step 4:  3 hospital phones ring simultaneously
Step 5:  Gemini parses each response in real-time
Step 6:  Best hospital selected with reason
Step 7:  Ambulance simulation shows movement on map
Step 8:  Hospital dashboard shows incoming patient details
Step 9:  "Patient delivered" — emergency closed
```

**Total time: ~90 seconds** (vs 15+ minutes manual)

---

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/emergency/identify` | Report emergency with photo |
| `GET /api/driver/{id}/dashboard` | Full driver view with navigation |
| `GET /api/hospital/{id}/status` | Hospital ER dashboard with patient card |
| `POST /api/hospital/{id}/confirm-bed` | Hospital confirms or denies bed |
| `POST /api/simulation/start` | Start ambulance movement simulation |
| `GET /api/simulation/status/{id}` | Live ambulance position for map |
| `GET /docs` | Full Swagger documentation (29 endpoints) |

---

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Add: GEMINI_API_KEY, TWILIO credentials, Firebase credentials

# Seed demo data
python -m scripts.seed_data

# Run
uvicorn app.main:app --port 8000

# Open docs
http://localhost:8000/docs
```

---

## Team

**Kairos AI** — Built for saving lives, not just winning hackathons.

---

*"Kairos" (Greek: καιρός) — the critical moment. The right time to act.*
