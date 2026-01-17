# DeltaWash
*A Raspberry Pi handwashing compliance system (WHO steps 2–7) with an optional hospital analytics dashboard.*

**2nd Overall Winner at Deltahacks 12**

---

## Overview

DeltaWash is a **Raspberry Pi–based system that monitors handwashing quality in real time** using computer vision.
It verifies that all critical hand surfaces are cleaned using the World Health Organization–recommended motions and provides **immediate visual feedback** at the sink, along with **aggregated compliance analytics** through a web dashboard.

The goal is to improve hand hygiene compliance by replacing guesswork with **clear, real-time guidance and measurable outcomes**.

---

## Motivation

Handwashing is the most effective way to prevent healthcare-associated infections, yet compliance remains inconsistent:

* Average handwashing compliance:
  * Nurses: ~75%
  * Doctors: ~63%
* Up to 15% of hospitalized patients in middle-income countries acquire a healthcare-associated infection
* Approximately 10% of those cases result in death

Most failures are not due to negligence, but to **incomplete technique** and lack of immediate feedback. DeltaWash addresses this gap.

---

## What DeltaWash Does

### Real-Time Handwashing Guidance

* Uses a camera above the sink to track hand motions
* Detects whether all required cleaning motions are performed
* Confirms each step only after it has been done **correctly and for sufficient duration**

### Immediate User Feedback

* LED indicators near the sink show live progress

  * Blinking LED: step in progress
  * Solid LED: step completed successfully
* Removes ambiguity about when a step is “done”

### Compliance Analytics

* Session results are sent to a central dashboard
* Supports:

  * Live compliance monitoring
  * Identification of commonly missed steps
  * Long-term trend analysis across devices or units

All hand tracking is anonymous and processed locally on-device.

---

## Handwashing Protocol (Simplified)

DeltaWash evaluates the core WHO-recommended hand-cleaning motions that ensure coverage of:

* Palms
* Backs of hands
* Between fingers
* Thumbs
* Fingertips

These motions are often referred to as **WHO steps 2–7**, but the system does not require users to know or memorize them — guidance is implicit through feedback.

---

## System Architecture

1. **Raspberry Pi + Camera**

   * Captures handwashing sessions
   * Runs all vision and inference locally

2. **On-Device ML Pipeline**

   * MediaPipe Hands for hand landmark detection
   * CNN + LSTM ensemble for motion classification
   * Real-time session state tracking

3. **Feedback Controller**

   * ESP8266 receives step status over WiFi
   * Drives LED indicators for user feedback

4. **Web Dashboard**

   * Receives summarized session data
   * Displays compliance statistics and trends

---

## Tech Stack

| Area               | Tools                                |
| ------------------ | ------------------------------------ |
| On-device pipeline | Python 3.11, OpenCV, MediaPipe Hands |
| ML models          | PyTorch / Torchvision, CNN + LSTM    |
| Hardware           | Raspberry Pi, Pi Camera, ESP8266     |
| Dashboard frontend | React, TypeScript, Vite              |
| Dashboard backend  | FastAPI, SQLAlchemy, Pydantic        |
| Database           | PostgreSQL                           |
| Local development  | Docker Compose                       |
| Testing            | pytest, Vitest, Playwright           |

---

## Repository Structure

```text
src/deltawash_pi/                # On-device detection pipeline + CLI
config/                          # YAML configuration files
hardware/esp8266/                # LED controller firmware
dashboard/                       # Web dashboard (frontend + backend)
docs/                            # Setup and deployment documentation
scripts/                         # Utility and demo scripts
```

---

## Running the Dashboard (Local)

```bash
docker compose -f dashboard/docker-compose.dashboard.yml up -d --build
```

* Frontend: [http://localhost:5173](http://localhost:5173)
* API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

More details: `docs/DASHBOARD_STARTUP.md`

---

## Running the Pi Pipeline

See `specs/001-handwash-compliance/quickstart.md` for full setup instructions.

Typical run:

```bash
python -m deltawash_pi.cli.capture --config config/local.yaml
```

---

## Notes

* All vision processing runs locally; no raw video is uploaded
* The dashboard is designed to support **synthetic/demo data** for multi-device testing
* Deployment is provider-agnostic (see `dashboard/DEPLOYMENT_GUIDE.md`)