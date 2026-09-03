# RecoverAI — Autonomous AI Revenue Recovery System

[![Build Status](https://github.com/aman-UI2006/RecoverAI/actions/workflows/ci.yml/badge.svg)](https://github.com/aman-UI2006/RecoverAI/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688.svg)](https://fastapi.tiangolo.com/)
[![React: 18](https://img.shields.io/badge/React-18-blue.svg)](https://react.dev/)
[![Razorpay Buildathon](https://img.shields.io/badge/Razorpay_Buildathon-Track_03_AI_Revenue_Recovery-0284c7.svg)](https://razorpay.com/)

> **Razorpay AI Buildathon — Track 03: AI Revenue Recovery**  
> An audit-verifiable, capability-aware, multi-tenant AI engine that autonomously diagnoses payment failures, optimizes candidate recovery actions using Expected Net Recovery Value ($ENRV$), and executes targeted recovery dispatches via Razorpay APIs.

---

## 1. Executive Summary

Every year, merchants lose up to **15–20% of potential revenue** to payment failures, checkout friction, subscription lapses, and abandoned invoices. Standard gateway retries are passive and blunt, applying identical retry logic regardless of failure cause.

**RecoverAI** replaces static retry rules with an intelligent 10-stage decision pipeline:
- **Incremental Lift:** Achieves a **`68.42%` Treatment Recovery Rate** vs **`22.10%` Baseline Control** (**`+46.32%` Incremental Recovery Rate Lift**; **210% relative improvement**).
- **Financial Impact:** Recovered **`₹ 3.94 Cr` Net Incremental Revenue** across a 25,000 treatment cohort post-refunds and intervention costs.
- **Strict Non-Bypassable Safety:** AI models provide purely advisory recommendations (`GroqLLMService`). Execution is strictly gated by a **Deterministic Policy Engine** (`PolicyEngine`) and merchant capability resolver (`CapabilityResolver`).
- **Cryptographic Auditability:** Every transaction transition generates a continuous SHA-256 tamper-evident hash chain (`AuditTrailService`) rooted at `GENESIS_HASH`.

---

## 2. System Architecture & 10-Stage Pipeline

```text
 ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
 │  1. DETECT  │ ──> │ 2. DIAGNOSE │ ──> │  3. DECIDE  │ ──> │4. CAPABILITY│ ──> │  5. POLICY  │
 └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                                        │
 ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐            │
 │  10. AUDIT  │ <── │ 9. MEASURE  │ <── │8. ATTRIBUTE │ <── │  7. VERIFY  │ <──────────┘
 └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘   6. EXECUTE
```

### Stage Summary
1. **DETECT:** Ingests webhooks (`/webhooks/razorpay`) and application events (`/app-event`) with ACID deduplication and HMAC-SHA256 signature verification.
2. **DIAGNOSE:** 4-level root cause classification cascade (Level 1 Deterministic Lookup $\rightarrow$ Level 2 XGBoost Classifier $\rightarrow$ Level 3 Groq LLM Fallback $\rightarrow$ Level 4 Human Review Queue).
3. **DECIDE:** Evaluates Expected Net Recovery Value ($ENRV(a_i) = P(\text{recovery} \mid X, a_i) \cdot \text{Amount} - \text{InterventionCost}(a_i)$) across candidate actions (`PAYMENT_LINK`, `RECOVERY_MESSAGE`, `WHATSAPP_REMINDER`, `RETRY`, `MANUAL_OUTREACH`, `NO_ACTION`).
4. **CAPABILITY:** Filters candidate actions against the merchant's active capability matrix (`CapabilityResolver`).
5. **POLICY:** Enforces business rules (`PolicyEngine`): max retry limits, cooldown periods, maximum action amounts, fraud gates.
6. **EXECUTE:** Dispatches authorized recovery actions via `RazorpayAdapter` (`POST /v1/payment_links`) with idempotency replay protection (`merchant_id:tx_id:cycle:action`).
7. **VERIFY:** Processes Razorpay webhooks (`payment_link.paid`, `payment.failed`, `payment_link.expired`) with HMAC verification.
8. **ATTRIBUTE:** Classifies payment recovery source (`DIRECT_REFERENCE`, `ATTRIBUTED`, or `UNATTRIBUTED`).
9. **MEASURE:** Computes financial lift, net revenue, and cohort analytics via `MeasurementEngine`.
10. **AUDIT:** Generates sequential SHA-256 tamper-evident hash chains ($H_n = \text{SHA256}(H_{n-1} \parallel \text{CanonicalJSON}(E_n))$).

---

## 3. Technology Stack & Key Libraries

- **Backend Framework:** FastAPI (Python 3.11 / 3.13)
- **Database & ORM:** PostgreSQL 16, SQLAlchemy 2.0 (AsyncIO), Alembic migrations
- **Caching & Locks:** Redis 7, `redis-py` (async lock fast-path & deduplication)
- **Machine Learning:** XGBoost, Scikit-Learn, Isotonic Regression calibration (`joblib`), Pandas, Parquet
- **LLM Provider:** Groq API (`groq/compound-mini` — Live authenticated)
- **Frontend Framework:** React 18, TypeScript, Vite 5, TailwindCSS, Lucide Icons, Recharts
- **Testing Suites:** Pytest (425 tests passing), Vitest (62 tests passing), Playwright 1.62.1
- **Containerization:** Docker, Docker Compose, Nginx reverse proxy

---

## 4. Comprehensive Documentation Index

All core system specifications are documented in the [`docs/`](docs/) directory:

- [**System Architecture Specification** (`docs/ARCHITECTURE.md`)](docs/ARCHITECTURE.md) — Exhaustive 10-stage pipeline, Mermaid sequence diagrams, state transitions, dual-mode operational guidelines.
- [**Buildathon Quantitative Evaluation Report** (`docs/EVALUATION.md`)](docs/EVALUATION.md) — 50,000 transaction simulation batch metrics, ML ROC-AUC (0.7934), Brier score (0.1595), gross & net revenue lift.
- [**Failure Analysis & Resilience Specification** (`docs/FAILURE_ANALYSIS.md`)](docs/FAILURE_ANALYSIS.md) — Detailed engineering analysis across all 25 failure modes in 5 system domains.
- [**Security & Safety Compliance Specification** (`docs/SECURITY.md`)](docs/SECURITY.md) — HMAC SHA-256 verification protocol, AI Air-Gap architecture, PII sanitization, RBAC matrix.
- [**Current Project Status** (`docs/PROJECT_STATUS.md`)](docs/PROJECT_STATUS.md) — Step-by-step verification history and current project milestone state.

---

## 5. Quickstart Setup & Local Development

### 5.1 Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 16+ & Redis 7+

### 5.2 Backend Setup
```bash
# 1. Clone repository
git clone https://github.com/aman-UI2006/RecoverAI.git
cd RecoverAI

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Configure environment variables
cp .env.example .env

# 5. Run database migrations
alembic upgrade head

# 6. Start FastAPI server
uvicorn backend.app.main:app --reload --port 8000
```
Backend API interactive OpenAPI docs will be available at: `http://localhost:8000/docs`

### 5.3 Frontend Setup
```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Start Vite development server
npm run dev
```
Frontend Web Dashboard will be available at: `http://localhost:5173`

---

## 6. Testing & Quality Verification

### Run Backend Pytest Suite (425 Tests)
```bash
python -m pytest backend/tests/
```

### Run Frontend Vitest Suite (62 Tests)
```bash
cd frontend
npx vitest run
```

### Build Production Assets
```bash
cd frontend
npm run build
```

---

## 7. Dual Operational Modes (`REAL_TEST` vs `SIMULATION`)

RecoverAI supports dual execution modes toggled via environment variable or UI:
- **`SIMULATION` Mode:** Uses synthetic transaction datasets (seed 42) and simulated payment link responses for high-throughput batch evaluation.
- **`REAL_TEST` Mode:** Connects live to Razorpay API endpoints (`POST /v1/payment_links`) using test-mode API credentials (`rzp_test_...`) and verifies real HMAC-SHA256 webhook signatures.

---

## 8. License

This project is open-source under the terms of the [MIT License](LICENSE).
