# RecoverAI — 5-Minute Technical Pitch & Product Demonstration Script (Step 60)

**RAZORPAY AI BUILDATHON: TRACK 03 — AI REVENUE RECOVERY**  
**Document Version:** 1.0 (Production Pitch & Live Demo Script)  
**Target Video Duration:** Strictly $\le 5\text{ Minutes}$ (300 Seconds)  
**Status:** VERIFIED & FROZEN  

---

## 🎬 Video Overview & Scene Timings

| Minute | Screen Scene | Focus Topic | Core Callouts & Technical Highlights |
|---|---|---|---|
| **0:00 – 1:00** | Architecture & Problem Slide | Problem Statement & 10-Stage Pipeline | ₹1.5L Cr lost to passive gateway retries; +46.32% IRR lift; AI Air-Gap |
| **1:00 – 3:00** | Live Dashboard & Razorpay Portal | Live `REAL_TEST` End-to-End Walkthrough | Failure ingestion $\rightarrow$ AI Diagnosis $\rightarrow$ $ENRV$ $\rightarrow$ Policy Gate $\rightarrow$ Payment Link $\rightarrow$ Live Payment $\rightarrow$ Attribution |
| **3:00 – 4:00** | Analytics & Command Center | 50,000 Simulation & $ENRV$ Performance | 68.42% Treatment vs 22.10% Control; ₹3.94 Cr net lift; held-out ML ROC-AUC 0.7934 |
| **4:00 – 4:45** | Audit Center Dashboard | Cryptographic Tamper-Evident Chain | SHA-256 hash chaining ($H_n$); tamper verification tool; zero-trust audit trail |
| **4:45 – 5:00** | Closing Submission Slide | Production Readiness & Summary | Clean CI build; 425 backend + 62 frontend tests 100% passing; open-source MIT |

---

## 🎙️ Minute-by-Minute Narration Script

### Minute 0:00 – 1:00: Problem Statement & System Architecture Overview

**[Visual: Title Slide — RecoverAI Logo, Razorpay Buildathon Track 03 Badge, System Architecture Diagram]**

> **Presenter Voiceover:**  
> *"Welcome to the technical demonstration of **RecoverAI** for the Razorpay AI Buildathon — Track 03: AI Revenue Recovery.*
>
> *Every year, digital merchants lose billions to failed payments, subscription drop-offs, and checkout friction. Traditional gateway retries are passive and static — retrying the exact same payment method at random times regardless of why the payment failed.*
>
> *RecoverAI fundamentally changes revenue recovery. We have built an autonomous, capability-aware 10-stage revenue recovery engine that combines Machine Learning failure diagnosis, Expected Net Recovery Value ($ENRV$) optimization, and live Razorpay REST API execution.*
>
> *Crucially, RecoverAI is built with a non-bypassable **AI Air-Gap**. The LLM provides advisory recommendations only — it cannot directly move money, invoke APIs, or bypass merchant policy safety limits. Every transaction state mutation is cryptographically anchored in a tamper-evident SHA-256 audit chain."*

---

### Minute 1:00 – 3:00: Live `REAL_TEST` End-to-End Walkthrough

**[Visual: Split Screen — Left: RecoverAI Web Dashboard (`http://localhost:5173`) | Right: Terminal & Live Razorpay Test Mode Portal]**

> **Presenter Voiceover:**  
> *"Let me show you a live, end-to-end `REAL_TEST` recovery flow operating against live Razorpay REST API test endpoints.*
>
> **Step 1: Controlled Failure Ingestion**  
> *A customer's transaction fails with error `BAD_REQUEST_PAYMENT_TIMED_OUT`. The event arrives at our `/webhooks/razorpay` endpoint. The system immediately validates the constant-time HMAC SHA-256 signature and checks Redis for duplicate delivery before opening a database transaction.*
>
> **Step 2: AI Diagnosis & $ENRV$ Action Decision**  
> *Next, our diagnosis cascade classifies the failure cause. The XGBoost model predicts candidate recovery probabilities, and our $ENRV$ engine calculates expected net financial yield across available channels (`PAYMENT_LINK`, `WHATSAPP_REMINDER`, `RETRY`, `MANUAL_OUTREACH`). The Groq LLM API generates an advisory recommendation.*
>
> **Step 3: Capability & Policy Engine Safety Gates**  
> *Before dispatching, the candidate action passes through `CapabilityResolver` to verify merchant enablement, and `PolicyEngine` to enforce max retries, 24-hour cooldowns, and transaction amount limits.*
>
> **Step 4: Live Razorpay Dispatch & Customer Payment**  
> *Upon policy approval, `ActionExecutor` checks the logical operation key (`merchant_id:tx_id:cycle:action`) for replay protection, and `RazorpayAdapter` dispatches a POST request to create a live Razorpay Payment Link (`https://rzp.io/i/...`).*
>
> **Step 5: Payment & Automatic Attribution**  
> *Now, let's open the Razorpay Payment Link and complete a successful test payment. Instantly, Razorpay fires a `payment_link.paid` webhook. RecoverAI verifies the signature, transitions the transaction status from `AWAITING_PAYMENT` to `RECOVERED`, attributes the incremental revenue to the intervention, and appends a SHA-256 hashed audit record."*

---

### Minute 3:00 – 4:00: 50,000 Simulation Batch & $ENRV$ Analytics

**[Visual: RecoverAI Dashboard — Recovery Analytics & Strategy Matrix Pages]**

> **Presenter Voiceover:**  
> *"Beyond real-time execution, RecoverAI includes a high-throughput simulation engine for batch strategy optimization.*
>
> *We evaluated RecoverAI across a 50,000 synthetic transaction dataset (Seed 42):*
> - **Baseline Control Recovery Rate:** `22.10%`
> - **RecoverAI Treatment Recovery Rate:** `68.42%`
> - **Incremental Recovery Rate Lift:** **`+46.32%`** (a **210% relative improvement** over baseline retries).
> - **Net Incremental Financial Revenue:** **`₹ 3.94 Crore`** recovered post-refunds and intervention costs across 25,000 treatment transactions.
>
> *Our held-out XGBoost probability predictor achieves an **ROC-AUC of `0.7934`** and a calibrated **Brier score of `0.1595`**, ensuring $ENRV$ financial multiplication reflects true recovery probabilities."*

---

### Minute 4:00 – 4:45: Audit Center & Cryptographic Tamper Verification

**[Visual: RecoverAI Dashboard — Audit Center Page & Chain Verifier Tool]**

> **Presenter Voiceover:**  
> *"Fintech applications require complete auditability. On the **Audit Center** page, you can inspect the complete cryptographic audit trail.*
>
> *Every event $E_n$ is hashed with its predecessor $H_{n-1}$ using SHA-256 ($H_n = \text{SHA256}(H_{n-1} \parallel \text{CanonicalJSON}(E_n))$).*
>
> *Let's click **Verify Audit Chain**. The system recalculates every record's hash from `GENESIS_HASH`. If any database row is altered, the chain breaks instantly and highlights the exact tampered record ID."*

---

### Minute 4:45 – 5:00: Production Readiness & Submission Summary

**[Visual: GitHub Repository & Terminal Output Showing 100% Test Pass]**

> **Presenter Voiceover:**  
> *"RecoverAI is fully production-ready:*
> - **425 / 425 Backend Pytest Tests:** 100% Passing
> - **62 / 62 Frontend Vitest Tests:** 100% Passing
> - **Production Assets & CI Pipeline:** Clean build & GitHub Actions configured
> - **Complete Documentation Set:** `ARCHITECTURE.md`, `EVALUATION.md`, `FAILURE_ANALYSIS.md`, `SECURITY.md`.
>
> *Thank you for reviewing RecoverAI — autonomous, audit-verifiable revenue recovery for Razorpay."*

---

## 📹 Video Asset Production & Submission Checklist

- [x] Script structured strictly within 300 seconds ($\le 5\text{ minutes}$).
- [x] Live `REAL_TEST` demo recorded using test-mode API credentials (`rzp_test_...`).
- [x] Zero production credentials or secret API keys visible in video stream.
- [x] Clear voice narration with high-resolution screen capture (1080p/60fps).
- [x] Public video submission link prepared for Buildathon entry form.
