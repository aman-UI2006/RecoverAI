# RecoverAI — Failure Analysis & Resilience Specification (Step 57)

**RAZORPAY AI BUILDATHON: TRACK 03 — AI REVENUE RECOVERY**  
**Document Version:** 1.0 (Exhaustive System Failure Matrix)  
**Status:** VERIFIED & FROZEN  

---

## 1. Executive Summary & Defensive Principles

**RecoverAI** is designed with defense-in-depth architectural patterns to handle payment gateway outages, adversarial attacks, high-concurrency event storms, LLM rate limits, and network dropouts without compromising financial state integrity or cryptographic audit trails.

### Core Defensive Engineering Principles
1. **Zero Financial Mutation on Unauthenticated Ingestion:** Webhook endpoints validate HMAC SHA-256 signatures before reading or writing to the database. Invalid requests are dropped immediately with HTTP `401 Unauthorized`.
2. **Atomic Rollback & State Isolation:** All state mutations execute within database transaction boundaries (`async with session.begin()`). Any database or application exception triggers an immediate `rollback()`, leaving zero partial mutations or orphan audit entries.
3. **Ambiguous Outcome Resolution (UNKNOWN Gate):** Gateway timeouts during external API execution do NOT retry automatically. State is mutated to `UNKNOWN` and queued for `ReconciliationEngine` polling.
4. **Deterministic LLM Fallback (Air-Gap):** If the Groq LLM API is unavailable or returns malformed JSON, the recommendation pipeline falls back deterministically to the top $ENRV$-ranked candidate action.
5. **Idempotency & Replay Protection:** Logical operation keys (`merchant_id:transaction_id:recovery_cycle:action`) backed by database `UNIQUE` indexes prevent duplicate recovery action dispatches under network retry conditions.

---

## 2. Exhaustive 25 System Failure Scenarios Matrix

```text
                               FAILURE DOMAINS (25 SCENARIOS)
┌─────────────────────────┬─────────────────────────┬─────────────────────────┐
│ DOMAIN 1: INGESTION     │ DOMAIN 2: CONCURRENCY   │ DOMAIN 3: AI / LLM      │
│ F-01 to F-05            │ F-06 to F-10            │ F-11 to F-15            │
└────────────┬────────────┴────────────┬────────────┴────────────┬────────────┘
             │                         │                         │
             └─────────────────────────┼─────────────────────────┘
                                       │
┌──────────────────────────────────────┴──────────────────────────────────────┐
│ DOMAIN 4: EXECUTION & ADAPTER        │ DOMAIN 5: ATTRIBUTION & RECONCIL    │
│ F-16 to F-20                         │ F-21 to F-25                        │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

---

### Domain 1: Ingestion & Webhook Authenticity Failures (F-01 – F-05)

#### F-01: Forged or Missing HMAC Signature
- **Detection:** `RazorpayAdapter.verify_webhook_signature()` computes HMAC SHA-256 over raw body bytes. Comparison fails.
- **Handling & State:** Request rejected immediately with `HTTP 401 Unauthorized`.
- **Database & Audit:** Zero database state mutation (no `Event`, `Transaction`, `AuditEvent`, or `RecoveryAttempt` created).
- **Verification Test:** `backend/tests/test_security_concurrency_resilience.py::test_1_forged_hmac_prevents_state_mutation`.

#### F-02: Duplicate Webhook Delivery / Event Storm
- **Detection:** Redis fast-path check (`redis.exists(idempotency_key)`) or PostgreSQL `event_deduplications` `UNIQUE(event_id)` index collision.
- **Handling & State:** Webhook handler catches duplicate error gracefully and returns `{"status": "ok", "is_duplicate": true}` with HTTP `200 OK`.
- **Database & Audit:** Second event payload discarded; zero state mutation or duplicate `RecoveryAttempt` generated.
- **Verification Test:** `backend/tests/test_security_concurrency_resilience.py::test_2_concurrent_100_duplicate_webhooks`.

#### F-03: Malformed Payload / Schema Validation Rejection
- **Detection:** FastAPI Pydantic schema validation catches missing fields, incorrect data types, or invalid JSON structure.
- **Handling & State:** Request rejected with HTTP `422 Unprocessable Content` (or HTTP `400 Bad Request`).
- **Database & Audit:** Zero database write; transaction state untouched.
- **Verification Test:** `backend/tests/test_security_concurrency_resilience.py::test_5_malicious_input_validation_rejection`.

#### F-04: Redis Outage / Fast-Path Degradation
- **Detection:** Redis connection raises `ConnectionRefusedError` or `TimeoutError`.
- **Handling & State:** `EventNormalizerService` catches Redis exception, logs warning, and degrades gracefully to PostgreSQL `event_deduplications` table check.
- **Database & Audit:** Deduplication correctness guaranteed via PostgreSQL `UNIQUE` index constraint boundary.
- **Verification Test:** `backend/tests/test_security_concurrency_resilience.py::test_3_redis_unavailable_fallback_to_postgres`.

#### F-05: Out-of-Order Webhook Event Delivery
- **Detection:** `StateTransitionService` receives event with timestamp older than existing transaction record or invalid state transition target.
- **Handling & State:** State machine checks transition matrix (`ALLOWED_TRANSITIONS`). Invalid backwards transition rejected cleanly.
- **Database & Audit:** Audit event logged for out-of-order delivery attempt; authoritative state preserved.
- **Verification Test:** `backend/tests/test_state_machine.py`.

---

### Domain 2: Concurrency & Database Failures (F-06 – F-10)

#### F-06: Concurrent Transaction Row-Lock Contention
- **Detection:** Multiple async worker tasks attempt to update the same transaction simultaneously.
- **Handling & State:** `StateTransitionService` executes `select(Transaction).where(Transaction.id == tx_id).with_for_update()`. Subsequent tasks block until lock releases.
- **Database & Audit:** Guarantees strict sequential state transitions and prevents audit chain hash forks.
- **Verification Test:** `backend/tests/test_audit_trail.py::test_concurrent_audit_logging`.

#### F-07: Mid-Transition Database Commit Failure
- **Detection:** Database connection drops or constraint violation occurs during `session.commit()`.
- **Handling & State:** Python `except` block catches exception, executes `await session.rollback()`, and raises mapped domain error.
- **Database & Audit:** All uncommitted changes reverted atomically; original transaction status preserved; zero orphan audit events.
- **Verification Test:** `backend/tests/test_security_concurrency_resilience.py::test_4_db_failure_atomic_rollback`.

#### F-08: Multi-Tenant Tenant Boundary Violation
- **Detection:** User/API request attempts to access or mutate a transaction belonging to another `merchant_id`.
- **Handling & State:** Database query enforces `.where(Model.merchant_id == current_user.merchant_id)`. Query returns zero rows (`404 Not Found`).
- **Database & Audit:** Zero cross-tenant data leak or unauthorized mutation.
- **Verification Test:** `backend/tests/test_security.py::test_multi_tenant_isolation`.

#### F-09: Cryptographic Audit Hash Chain Tampering
- **Detection:** `AuditTrailService.verify_chain(transaction_id)` re-computes $H_n = \text{SHA256}(H_{n-1} \parallel \text{CanonicalJSON}(E_n))$ and finds mismatch.
- **Handling & State:** Verification function flags `valid: False` and identifies exact tampered `audit_event_id` and sequence index.
- **Database & Audit:** Tamper alert raised in system security logs.
- **Verification Test:** `backend/tests/unit/test_audit_hash.py`.

#### F-10: Execution Operation Key Collision
- **Detection:** `ActionExecutor` attempts inserting duplicate `logical_operation_key` (`merchant_id:tx_id:cycle:action`).
- **Handling & State:** DB `UNIQUE` index raises `IntegrityError`. Executor catches exception and returns existing attempt status.
- **Database & Audit:** Prevents duplicate Razorpay API payment link creation races.
- **Verification Test:** `backend/tests/test_action_executor.py`.

---

### Domain 3: AI / LLM & Intelligence Failures (F-11 – F-15)

#### F-11: Groq LLM API Outage / Rate Limit (`HTTP 429 / 503`)
- **Detection:** `GroqLLMService` API call raises `RateLimitError` or HTTP connection timeout.
- **Handling & State:** `StructuredAIRecommender` catches exception, logs warning, and falls back deterministically to top $ENRV$-ranked action.
- **Database & Audit:** Recommendation generated with `fallback_applied: True`; state mutates safely to `INTERVENTION_SELECTED`.
- **Verification Test:** `backend/tests/test_ai_recommender.py::test_groq_api_fallback`.

#### F-12: Groq LLM Invalid Schema / Pydantic Parse Failure
- **Detection:** Groq response fails Pydantic validation (`AIRecommendationResponse.model_validate_json`).
- **Handling & State:** Fallback mechanism extracts top action from `ENRVCalculationResponse` and constructs valid fallback response.
- **Database & Audit:** Advisory recommendation populated safely; air-gap integrity maintained.
- **Verification Test:** `backend/tests/ai/test_ai_schemas.py`.

#### F-13: ML Model Artifact Loading Failure
- **Detection:** `joblib.load()` fails due to missing file or corrupt model artifact.
- **Handling & State:** `ActionConditionalPredictor` falls back to baseline heuristic scoring matrix based on historical scenario success rates.
- **Database & Audit:** System continues serving recovery recommendations without crash.
- **Verification Test:** `backend/tests/test_action_conditional_model.py`.

#### F-14: Zero Historical Context / Cold-Start Merchant
- **Detection:** Transaction feature vector contains unknown merchant ID or zero prior transaction history.
- **Handling & State:** `FeatureExtractor` imputes missing features with neutral default baselines (`historical_success_rate = 0.50`, `prior_attempts = 0`).
- **Database & Audit:** Cold-start transaction successfully processed through $ENRV$ and policy evaluation.
- **Verification Test:** `backend/tests/test_feature_extractor.py`.

#### F-15: Out-of-Bound Probability Estimates
- **Detection:** ML model outputs probability prediction $< 0.0$ or $> 1.0$.
- **Handling & State:** Predictor applies explicit clipping: `np.clip(prob, 0.0, 1.0)`.
- **Database & Audit:** Probabilities guaranteed valid for downstream $ENRV$ financial multiplication.
- **Verification Test:** `backend/tests/unit/test_enrv.py`.

---

### Domain 4: Execution & External Integration Failures (F-16 – F-20)

#### F-16: Razorpay Gateway Network Timeout / Ambiguous HTTP 5xx
- **Detection:** `RazorpayAdapter` HTTP POST request times out or receives `HTTP 502 / 503 / 504`.
- **Handling & State:** `ActionExecutor` catches timeout, sets execution status to `UNKNOWN`, and mutates transaction state to `UNKNOWN`.
- **Database & Audit:** Scheduled `ReconciliationEngine` worker enqueues transaction for external status verification polling.
- **Verification Test:** `backend/tests/test_reconciliation_engine.py`.

#### F-17: Expired / Invalid Razorpay API Key (`HTTP 401`)
- **Detection:** Razorpay REST API returns `401 Unauthorized` (bad `key_id` or `key_secret`).
- **Handling & State:** `RazorpayAdapter` maps error to non-retryable `ExecutionStatus.FAILURE`. State mutates to `HUMAN_REVIEW` or `FAILED`.
- **Database & Audit:** Prevents continuous fruitless API retry loops under invalid credentials.
- **Verification Test:** `backend/tests/test_razorpay_adapter.py`.

#### F-18: Unsupported Action Capability Requested
- **Detection:** `CapabilityResolver` checks merchant capability matrix (e.g., `WHATSAPP_REMINDER` disabled for merchant).
- **Handling & State:** Action denied. System routes transaction to `HUMAN_REVIEW` queue for operator decision.
- **Database & Audit:** State mutates to `HUMAN_REVIEW`; audit trail records capability rejection.
- **Verification Test:** `backend/tests/test_capability_resolver.py`.

#### F-19: Razorpay API Rate Limiting (`HTTP 429`)
- **Detection:** Razorpay returns `HTTP 429 Too Many Requests` with `Retry-After` header.
- **Handling & State:** `RazorpayAdapter` executes exponential backoff with random jitter up to max 3 retries before returning `UNKNOWN`.
- **Database & Audit:** Protects API quota limits under peak throughput.
- **Verification Test:** `backend/tests/test_razorpay_adapter.py`.

#### F-20: Merchant Safety Policy Threshold Violation
- **Detection:** `PolicyEngine` detects transaction amount $> \text{MaxAmount}$ or recovery attempts $> \text{MaxRetries}$.
- **Handling & State:** Policy evaluation returns `REJECTED`. Transaction state mutates to `HUMAN_REVIEW` or `STOPPED`.
- **Database & Audit:** Execution blocked; policy failure reason persisted in `policy_evaluations` table.
- **Verification Test:** `backend/tests/test_policy_engine.py`.

---

### Domain 5: Outcome Resolution, Attribution & Escalation Failures (F-21 – F-25)

#### F-21: Unlinked Payment Webhook Event
- **Detection:** `ResultProcessor` receives valid webhook for `payment_link.paid` but reference ID matches no existing transaction.
- **Handling & State:** Processor logs unlinked event for audit inspection and returns HTTP `200 OK`.
- **Database & Audit:** Zero unhandled exception; zero state corruption of unrelated transactions.
- **Verification Test:** `backend/tests/test_result_processor.py`.

#### F-22: Multiple Payment Links Generated for Single Transaction
- **Detection:** Customer attempts paying an older payment link after a newer link was dispatched.
- **Handling & State:** `AttributionEngine` enforces `(transaction_id, recovery_attempt_id)` `UNIQUE` constraint and attributes first valid payment.
- **Database & Audit:** Duplicate payments marked `UNATTRIBUTED` or routed to merchant refund handling.
- **Verification Test:** `backend/tests/test_attribution_engine.py`.

#### F-23: Expired Payment Link Window Lapsed
- **Detection:** Razorpay sends `payment_link.expired` webhook event.
- **Handling & State:** `ResultProcessor` updates execution status to `EXPIRED` and mutates transaction state to `EXPIRED`.
- **Database & Audit:** Recovery cycle closed; transaction eligible for subsequent policy retry check if within limits.
- **Verification Test:** `backend/tests/test_result_processor.py`.

#### F-24: Human Review Queue Item Expiration
- **Detection:** Operator fails to review transaction in `human_reviews` table within 48 hours.
- **Handling & State:** Scheduled background cleanup worker updates review status to `EXPIRED` and mutates transaction to `STOPPED`.
- **Database & Audit:** Prevents transactions from lingering indefinitely in pending queue.
- **Verification Test:** `backend/tests/test_human_review.py`.

#### F-25: Reconciliation Engine Worker Network Failure
- **Detection:** `ReconciliationWorker` encounters network exception while polling external Razorpay API for `UNKNOWN` transactions.
- **Handling & State:** Worker logs error, updates `last_polled_at` timestamp, and releases lock for next scheduled cycle.
- **Database & Audit:** Transaction state remains safely in `RECONCILIATION` until definitive status verified.
- **Verification Test:** `backend/tests/test_reconciliation_engine.py`.

---

## 3. Detailed Technical Deep-Dives

### 3.1 External Gateway Timeout Handling (`ReconciliationEngine`)
When an external HTTP request to Razorpay times out during `ActionExecutor` dispatch:
1. `ActionExecutor` does NOT create another payment link or assume failure.
2. `RecoveryAttempt.execution_status` is updated to `UNKNOWN`.
3. `StateTransitionService` mutates transaction state: `EXECUTING` $\rightarrow$ `UNKNOWN`.
4. `ReconciliationWorker` polls `GET /v1/payment_links/{id}` asynchronously with exponential backoff.
5. Once verified:
   - If paid $\rightarrow$ state mutates to `RECOVERED` and triggers `AttributionEngine`.
   - If expired/failed $\rightarrow$ state mutates to `EXPIRED` or `FAILED`.

### 3.2 HMAC Signature Failure Handling
For raw request body $B$ and secret $K$:

$$S_{\text{expected}} = \text{HMAC-SHA256}(K, B)$$

1. Request header `X-Razorpay-Signature` ($S_{\text{received}}$) is extracted.
2. `hmac.compare_digest(S_{\text{expected}}, S_{\text{received}})` executes in constant time.
3. If `False` $\rightarrow$ handler raises `HTTPException(status_code=401, detail="Invalid signature")`.
4. Webhook processing halts immediately before parsing JSON or executing database queries.

### 3.3 Database Lock Conflict Mitigation (`SELECT ... FOR UPDATE`)
To prevent concurrent race conditions during state transitions and audit hash chain updates:

```python
stmt = (
    select(Transaction.id)
    .where(Transaction.id == transaction_id)
    .with_for_update()
)
await session.execute(stmt)
```

This guarantees that:
- Exactly one worker can mutate a transaction at any time.
- Audit event hashes $H_n = \text{SHA256}(H_{n-1} \parallel \text{CanonicalJSON}(E_n))$ remain strictly linear with zero branching.

### 3.4 Fallback Paths for LLM API Outages
If Groq API calls fail (network disconnect, rate limit HTTP 429, invalid JSON format):

```text
  Groq LLM Request
         │
         ▼
  [API Call Success?] ─── YES ───> Return AI Recommendation
         │
         NO
         │
         ▼
  Catch Exception & Log Warning
         │
         ▼
  Extract Top ENRV Candidate Action
         │
         ▼
  Construct Deterministic Fallback AIRecommendationResponse
         │
         ▼
  Proceed to CapabilityResolver & PolicyEngine
```
