# RecoverAI — Comprehensive Security & Safety Specification (Step 58)

**RAZORPAY AI BUILDATHON: TRACK 03 — AI REVENUE RECOVERY**  
**Document Version:** 1.0 (Authoritative Security & Safety Compliance Baseline)  
**Status:** VERIFIED & FROZEN  

---

## 1. Executive Summary & Security Philosophy

**RecoverAI** is built for high-trust fintech environments, where state corruption, unauthorized financial dispatches, data leakage, and AI prompt injection pose existential risks. The architecture enforces zero-trust boundaries at every tier.

### Core Security Guarantees
1. **Constant-Time HMAC Webhook Authenticity:** Inbound webhooks from Razorpay or external applications are validated using HMAC SHA-256 signatures over raw HTTP request body bytes before parsing JSON or executing database queries. Unauthenticated payloads are dropped immediately with `HTTP 401 Unauthorized`.
2. **Non-Bypassable AI Air-Gap Architecture:** The AI/LLM engine (`GroqLLMService`) is strictly an advisory component with ZERO capability to call external APIs, mutate payment state, issue payment links, or bypass policy rules.
3. **Deterministic Policy Safety Gates:** Every recovery action must pass through `CapabilityResolver` (merchant capability check) and `PolicyEngine` (business limits, cooldowns, max retries) prior to execution.
4. **Strict PII Minimization & Sanitization:** Sensitive customer identifiers (email, phone, card details) are masked or anonymized before feature extraction and prompt synthesis.
5. **Cryptographic Tamper-Evident Audit Chaining:** Every state transition generates a SHA-256 hashed audit log record linked sequentially to its predecessor, guaranteeing tamper-evident audit trails.

---

## 2. Inbound Webhook Security & HMAC SHA-256 Verification

### 2.1 Verification Protocol
Razorpay webhooks transmit an `X-Razorpay-Signature` header containing a hex-encoded HMAC-SHA256 digest computed over the exact raw request payload using the merchant's secret key.

```text
  HTTP Request Payload (Raw Bytes)
                │
                ▼
  [Compute HMAC-SHA256(RawBytes, Secret)]
                │
                ▼
  [Constant-Time hmac.compare_digest(Computed, HeaderSignature)]
                │
         ┌──────┴──────┐
        YES            NO
         │             │
         ▼             ▼
  Proceed to DB     HTTP 401 Unauthorized
  & Deduplication   Immediate Drop (Zero DB Write)
```

### 2.2 Constant-Time Comparison Implementation
To prevent timing attacks that inspect string comparison byte-by-byte, RecoverAI uses Python's built-in `hmac.compare_digest`:

```python
def verify_webhook_signature(raw_body: bytes, header_signature: str, secret: str) -> bool:
    computed_signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed_signature, header_signature)
```

- **Execution Order:** Signature verification executes in FastAPI middleware/endpoint BEFORE calling `request.json()` or opening a PostgreSQL transaction.
- **State Protection:** Prevents CPU/memory exhaustion and database state mutation from unauthenticated forgery attempts.

---

## 3. AI Air-Gap Architecture & Safety Isolation

### 3.1 Non-Bypassable Execution Pipeline
RecoverAI strictly isolates AI recommendations from execution primitives. The LLM has zero network or code permissions to invoke Razorpay REST APIs directly.

```text
 ┌─────────────────┐
 │ Groq LLM Engine │ (ADVISORY ONLY — Pure Text / JSON output)
 └────────┬────────┘
          │ Advisory Recommendation: { recommended_action, confidence_score }
          ▼
 ┌─────────────────────────┐
 │ Structured AI Validator │ (Validates JSON schema & Pydantic bounds)
 └────────┬────────────────┘
          │ Validated Candidate Action
          ▼
 ┌─────────────────────┐
 │ Capability Resolver │ (Enforces merchant capability enablement)
 └────────┬────────────┘
          │ Allowed Action
          ▼
 ┌───────────────┐
 │ Policy Engine │ (Enforces MaxRetries, Cooldown, MaxAmount)
 └────────┬──────┘
          │ APPROVED Action
          ▼
 ┌─────────────────┐
 │ Action Executor │ (Checks DB Idempotency Key)
 └────────┬────────┘
          │ Unique Dispatch
          ▼
 ┌──────────────────┐
 │ Razorpay Adapter │ (Executes REST API call to POST /v1/payment_links)
 └──────────────────┘
```

### 3.2 Air-Gap Safety Rules
1. **Zero Direct API Binding:** Groq LLM code has no access to Razorpay API keys, database sessions, or HTTP client sessions.
2. **Deterministic Fallback Gate:** If Groq LLM returns malformed JSON, times out, or encounters HTTP 429 rate limits, `StructuredAIRecommender` falls back to top $ENRV$-ranked action without crashing.
3. **Pydantic Validation Guard:** Output fields (`confidence_score`, `recommended_action`) are parsed through Pydantic schemas. Out-of-list or out-of-bound recommendations are rejected.

---

## 4. Deterministic Policy Engine Hierarchy

### 4.1 Policy Evaluation Flow
`PolicyEngine` evaluates candidate actions against a hierarchy of deterministic rules. If ANY rule fails, the candidate action is REJECTED.

```text
               Candidate Recovery Action
                           │
                           ▼
          [Rule 1: Merchant Capability Check] ─── FAIL ───> REJECT
                           │ PASS
                           ▼
          [Rule 2: Max Retry Count Check]     ─── FAIL ───> REJECT / HUMAN_REVIEW
                           │ PASS
                           ▼
          [Rule 3: Cooldown Period Check]     ─── FAIL ───> REJECT
                           │ PASS
                           ▼
          [Rule 4: Max Transaction Amount]    ─── FAIL ───> REJECT / HUMAN_REVIEW
                           │ PASS
                           ▼
          [Rule 5: Fraud / Risk Gate]        ─── FAIL ───> REJECT / STOPPED
                           │ PASS
                           ▼
                 APPROVE FOR EXECUTION
```

### 4.2 Policy Rule Specifications

| Policy Rule Name | Parameter | Description | Violation Outcome |
|---|---|---|---|
| **Max Retry Limit** | `max_attempts` (Default: 3) | Limits maximum intervention attempts per transaction | State mutates to `HUMAN_REVIEW` |
| **Cooldown Window** | `cooldown_hours` (Default: 24h) | Minimum delay between intervention dispatches | Action rejected; attempt postponed |
| **Max Action Amount** | `max_amount` (Default: ₹ 5,00,000) | Caps monetary value for automated recovery links | State mutates to `HUMAN_REVIEW` |
| **Allowed Action Types** | `enabled_actions` list | Merchant-configurable allowed recovery channels | Action rejected; fallback selected |
| **Fraud Risk Gate** | `risk_score` threshold | Rejects transactions with elevated fraud markers | State mutates to `STOPPED` |

---

## 5. PII Minimization & Data Anonymization

### 5.1 Privacy Protection Protocol
To comply with data protection standards and prevent sensitive data leakage to external LLM providers (Groq API), RecoverAI applies strict PII minimization:

```text
Raw Transaction Context
├── Customer Email: "john.doe@example.com"    ──> Anonymized: "j***e@example.com"
├── Customer Phone: "+919876543210"           ──> Anonymized: "+91******3210"
├── Customer Name:  "John Doe"                ──> Redacted:   "[REDACTED]"
└── Customer ID:    "cust_999888"             ──> Hashed:     "hash_a8f9c1..."
```

### 5.2 LLM Prompt Sanitization
Prompts transmitted to `GroqLLMService` contain ONLY:
- Failure scenario category (`PAYMENT_FAILURE`, `SUBSCRIPTION_LAPSE`, etc.)
- Standardized Razorpay error code (`BAD_REQUEST_PAYMENT_TIMED_OUT`)
- Minor-unit amount & currency (`250000 INR`)
- Numerical retry count & feature vector values

No raw customer emails, phone numbers, names, or street addresses are ever transmitted across external LLM boundaries.

---

## 6. Authentication, Authorization & RBAC

### 6.1 Multi-Tenant Identity Model
Authentication relies on signed JWT Bearer Tokens (`HS256`) or `X-API-Key` headers.

```json
{
  "sub": "user_operator_01",
  "merchant_id": "m_alpha_123",
  "role": "ROLE_OPERATOR",
  "iat": 1770000000,
  "exp": 1770086400
}
```

### 6.2 Role-Based Access Control (RBAC) Matrix

| Endpoint Group | `ROLE_ADMIN` | `ROLE_OPERATOR` | `ROLE_VIEWER` | `ROLE_MERCHANT` |
|---|:---:|:---:|:---:|:---:|
| **`GET /api/v1/transactions`** | All Merchants | Assigned Scope | Assigned Scope | Own `merchant_id` Only |
| **`POST /api/v1/recovery-actions`** | Yes | Yes | Read-Only (Denied) | Own `merchant_id` Only |
| **`POST /api/v1/human-reviews/{id}`** | Yes | Yes | Read-Only (Denied) | Denied |
| **`GET /api/v1/audit/chain/{id}`** | Yes | Yes | Yes | Own `merchant_id` Only |
| **`PUT /api/v1/merchant/config`** | Yes | Denied | Denied | Own `merchant_id` Only |

### 6.3 Multi-Tenant Isolation Enforcement
In FastAPI router dependencies, tenant resolution enforces `merchant_id` scoping:

```python
async def get_current_merchant(identity: AuthenticatedIdentity = Depends(get_current_identity)) -> Optional[str]:
    if identity.role == RoleEnum.ROLE_ADMIN.value:
        return identity.merchant_id
    if identity.merchant_id:
        return identity.merchant_id
    raise HTTPException(status_code=403, detail="Merchant role account lacks associated merchant tenant ID")
```

All SQL queries append `.where(Model.merchant_id == merchant_id)`. Client-supplied request headers or query parameters CANNOT override identity token `merchant_id`.

---

## 7. Secret Management & Infrastructure Security

1. **Zero Secret Hardcoding:** API keys, database credentials, and JWT signing keys are loaded strictly from system environment variables (`.env` file via `pydantic-settings`).
2. **Git Version Control Isolation:** `.env` is specified in `.gitignore`. Only `.env.example` containing non-secret placeholder variables is committed.
3. **Container Hardening:** Backend Docker images use multi-stage builds and execute as non-root user (`appuser:10001`).
4. **Nginx Reverse Proxy Security Headers:**
   - `X-Frame-Options: DENY`
   - `X-Content-Type-Options: nosniff`
   - `X-XSS-Protection: 1; mode=block`
   - `Referrer-Policy: strict-origin-when-cross-origin`
