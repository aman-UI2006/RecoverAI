# RecoverAI — FINAL PRE-IMPLEMENTATION CORRECTIONS
## Razorpay AI Buildathon — Track 03: AI Revenue Recovery

**Status:** FINAL / FROZEN  
**Purpose:** Authoritative correction overlay for the existing `implementation_plan.md`.  
**Rule:** Apply these corrections to the existing 61-step implementation plan. Do not redesign, reorder, merge, or remove the 61 steps.

---

# 0. FREEZE RULE

The existing RecoverAI architecture remains frozen:

`DETECT → DIAGNOSE → DECIDE → EXECUTE → MEASURE → AUDIT / STOP`

The following corrections are the **only** pre-implementation changes permitted after this review.

No new architecture, framework, database strategy, execution mode, or roadmap phase may be introduced unless a later verified blocker makes implementation impossible.

---

# 1. RAZORPAY WEBHOOK EVENT VERIFICATION

## Authoritative rule

RecoverAI must use only Razorpay webhook event names that are verified against the current official Razorpay documentation at implementation time.

For the Payment Link recovery flow:

- `payment_link.paid` is the authoritative Payment Link success event for this flow.
- Payment webhook events such as `payment.captured` and `payment.failed` may be subscribed to when they are required by the implementation.
- The implementation MUST NOT infer, invent, or rename Razorpay event types.

The raw Razorpay webhook body must be preserved for signature verification before JSON parsing.

### Required implementation rule

```text
Razorpay webhook
      ↓
capture raw bytes
      ↓
HMAC verification
      ↓
event-type validation
      ↓
deduplication
      ↓
normalization
      ↓
state transition
```

### Security

Webhook verification must use the configured webhook secret and constant-time comparison.

If the signature is invalid:

```text
HTTP 401
NO STATE MUTATION
NO EXECUTION
AUDIT SECURITY EVENT
```

---

# 2. REAL_TEST DEMO — DETERMINISTIC FAILURE INJECTION

The previous wording "trigger a real Test Mode payment failure" is too ambiguous.

## Authoritative REAL_TEST demo flow

RecoverAI's primary demo MUST use a controlled, deterministic failure event as the initial revenue-at-risk trigger.

```text
CONTROLLED TEST FAILURE EVENT
          ↓
EVENT INGESTION
          ↓
REVENUE AT RISK
          ↓
DIAGNOSIS
          ↓
ACTION-CONDITIONAL ENRV
          ↓
CAPABILITY RESOLVER
          ↓
POLICY ENGINE
          ↓
PAYMENT_LINK
          ↓
RAZORPAY TEST MODE PAYMENT
          ↓
payment_link.paid
          ↓
PAYMENT VERIFICATION
          ↓
ATTRIBUTION
          ↓
RECOVERED
```

### Important distinction

The initial failure may be a controlled application/test event.

The recovery itself MUST use the actual Razorpay Test Mode Payment Link flow.

This gives the demo:

- deterministic failure generation;
- real Razorpay Test Mode API execution;
- real Payment Link creation;
- real test checkout;
- real Razorpay webhook evidence;
- verifiable recovery attribution.

### Optional secondary demo

If a documented Razorpay Test Mode payment-failure mechanism is available and stable, it may be demonstrated as an additional scenario.

It must NOT be the sole dependency of the five-minute demo.

---

# 3. PAYMENT LINK IS NOT RECOVERY

Creating a Payment Link is an intervention.

It is NOT recovered revenue.

The only valid sequence is:

```text
Payment Link CREATED
        ↓
Customer payment
        ↓
Verified payment state
        ↓
Attribution evaluation
        ↓
Recovered revenue
```

Dashboard metrics MUST NOT increase recovered revenue when only a Payment Link has been created.

---

# 4. REAL_TEST CAPABILITY BOUNDARY

## REAL_TEST executable recovery capabilities

The authoritative real executable recovery capability is:

```text
PAYMENT_LINK
```

The following remain restricted unless independently verified and implemented:

```text
RETRY
SUBSCRIPTION_RECOVERY
AUTOMATED_GATEWAY_RETRY
```

They MUST NOT be presented as real Razorpay execution merely because they exist in the simulation action catalogue.

Internal actions remain valid:

```text
STOP
ESCALATE
HUMAN_REVIEW
```

## SIMULATION action catalogue

Simulation may evaluate:

```text
PAYMENT_LINK
RECOVERY_MESSAGE
SUBSCRIPTION_RECOVERY
RETRY
SMART_RETRY_SCHEDULE
DISCOUNT_NUDGE
STOP
ESCALATE
```

These are simulation strategies unless explicitly marked as verified executable capabilities.

---

# 5. RECOVERY_MESSAGE CORRECTION

`RECOVERY_MESSAGE` is an application-level communication strategy, not a Razorpay Payment Link API capability.

Therefore:

### REAL_TEST

```text
RECOVERY_MESSAGE = INTERNAL / DEMO-ONLY COMMUNICATION ACTION
```

It must not be represented as a verified Razorpay communications API unless a separate official integration is implemented and verified.

### SIMULATION

`RECOVERY_MESSAGE` may be evaluated as a strategy.

The simulator may model:

- message delivery;
- customer response;
- recovery probability;
- intervention cost;
- attribution window.

The UI must label this clearly as:

`SIMULATION STRATEGY`

unless an actual external messaging provider is integrated.

---

# 6. FOUR-SCENARIO EXECUTION BOUNDARY

RecoverAI supports four revenue-at-risk scenarios:

1. `PAYMENT_FAILURE`
2. `CHECKOUT_ABANDONMENT`
3. `SUBSCRIPTION_FAILURE`
4. `OVERDUE_RECEIVABLE`

But broad strategy evaluation belongs primarily to SIMULATION.

| Scenario | REAL_TEST | SIMULATION |
|---|---|---|
| Payment failure | Payment Link recovery | Full strategy catalogue |
| Checkout abandonment | Payment Link where appropriate | Full strategy catalogue |
| Subscription failure | Observe supported lifecycle; no invented retry | Full strategy catalogue |
| Overdue receivable | Payment Link where applicable | Full strategy catalogue |

Never fake an external Razorpay execution for a capability that has not been verified.

---

# 7. AUDIT TRAIL TERMINOLOGY CORRECTION

Use:

**Tamper-Evident SHA-256 Hash-Chained Audit Trail**

Do NOT use the following as an absolute technical claim:

- "immutable database"
- "cryptographically immutable"
- "impossible to alter"
- "tamper-proof"

## Correct technical model

```text
Canonical Audit Record
        +
Sequence Number
        +
Previous Hash
        ↓
SHA-256
        ↓
Current Event Hash
```

The first record is anchored using:

`GENESIS_HASH`

The chain provides evidence of modification because changing an earlier record breaks subsequent hash relationships.

It does NOT make a privileged database administrator mathematically incapable of rewriting the entire database.

### Dashboard wording

Use:

> "Tamper-evident audit chain"

not:

> "Immutable audit ledger"

---

# 8. AUDIT CHAIN CONCURRENCY

The audit service MUST serialize hash-chain writes.

Required properties:

- monotonic sequence number;
- previous-hash reference;
- database transaction;
- row-level locking or equivalent serialization;
- canonical JSON representation;
- deterministic hash input;
- chain verification endpoint.

Verification must detect:

```text
VALID CHAIN
BROKEN CHAIN
MISSING SEQUENCE
HASH MISMATCH
```

---

# 9. POLICY DEFAULTS ARE CONFIGURATION, NOT UNIVERSAL BUSINESS TRUTH

The following are demonstration defaults:

```text
max_auto_action_amount = ₹50,000
min_recovery_probability = 0.15
max_recovery_attempts = 3
cooldown_hours = 24
attribution_window_hours = 72
```

They MUST be implemented as:

- versioned configuration;
- merchant-configurable where applicable;
- auditable;
- persisted with the decision context;
- never hard-coded into business logic.

Use:

```text
DEFAULT DEMO POLICY v1
```

rather than presenting these numbers as universal Razorpay policy.

---

# 10. FINANCIAL DATA TYPE RULE

All monetary values MUST use:

```text
DECIMAL / NUMERIC(12,2)
```

or integer minor currency units.

Never use floating-point types for authoritative monetary amounts.

Probabilities may use floating-point values.

---

# 11. ATTRIBUTION CORRECTION

Operational lifecycle status and attribution classification remain separate.

## Operational status

Examples:

```text
AT_RISK
DIAGNOSED
EXECUTING
UNKNOWN
RECONCILIATION_REQUIRED
RECOVERED
FAILED
REFUNDED
STOPPED
ESCALATED
```

## Attribution classification

Examples:

```text
ATTRIBUTED
NATURAL_RECOVERY
CONTROL
UNATTRIBUTED
```

`CONTROL` is a cohort assignment / measurement classification, NOT a transaction lifecycle status.

---

# 12. ATTRIBUTION RULES

A payment is `ATTRIBUTED` only when the system has evidence linking the recovery to an intervention.

Preferred evidence hierarchy:

```text
1. DIRECT_REFERENCE
2. WINDOW_MATCH + valid intervention evidence
3. NATURAL_RECOVERY
4. UNATTRIBUTED
```

For Payment Link recovery:

```text
payment_link_id
        ↓
recovery_attempt
        ↓
verified payment
        ↓
DIRECT_REFERENCE
        ↓
ATTRIBUTED
```

Payment Link creation alone is insufficient.

---

# 13. CONTROL / TREATMENT METHODOLOGY

The evaluation framework must distinguish:

```text
CONTROL
vs
TREATMENT
```

Control must be a cohort assignment, not an attribution status.

## Preferred evaluation design

```text
Eligible population
        ↓
Deterministic/random assignment
        ├──────────────┐
        ↓              ↓
     CONTROL       TREATMENT
        ↓              ↓
 Baseline policy   RecoverAI
        ↓              ↓
 Outcome          Outcome
        └──────┬───────┘
               ↓
     Incremental comparison
```

The same eligibility criteria and evaluation window must apply to both groups.

If randomization is not used, the result must be described as an observational estimate rather than guaranteed causal attribution.

---

# 14. INCREMENTAL RECOVERY CLAIMS

Use:

```text
Treatment Recovery Rate
-
Control Recovery Rate
=
Incremental Recovery Rate
```

Then:

```text
Incremental Recovery Rate
×
Treatment Eligible Amount
=
Estimated Incremental Recovered Revenue
```

Finally:

```text
Estimated Incremental Recovered Revenue
-
Refunds
-
Intervention Costs
=
Net Incremental Recovery
```

The dashboard MUST label this as:

`Estimated Incremental Recovery`

unless the evaluation design supports a stronger causal claim.

Do not claim:

> "RecoverAI caused ₹X"

unless the experiment design justifies that causal statement.

---

# 15. 50K+ SIMULATION REQUIREMENTS

The synthetic evaluation must remain fully separate from REAL_TEST.

Required metadata:

```text
evaluation_run_id
dataset_version
dataset_size
random_seed
model_version
feature_version
policy_version
configuration_version
code_commit_sha
mode = SIMULATION
```

Required minimum dataset:

```text
50,000 records
```

Required split:

```text
70% Train
15% Validation
15% Test
```

with zero customer leakage across evaluation partitions.

---

# 16. SIMULATION MUST NOT LEAK THE ANSWER

The synthetic generator MUST NOT create a feature that directly encodes the outcome.

For example, do not provide:

```text
will_recover = 1
```

as a model input.

Outcome generation must happen after feature generation and action selection.

The action-conditional model must estimate:

`P(recovery | features, action)`

rather than simply reading a hidden recovery label.

---

# 17. ACTION-CONDITIONAL ML

The core model remains:

`P(recovery | X, action)`

Candidate actions are scored independently.

ENRV:

```text
ENRV(action)
=
P(recovery | X, action) × Amount
-
InterventionCost
-
OperationalCost
-
ExpectedRefundCost
```

The AI recommender ranks or explains candidate actions.

The AI does NOT execute them.

---

# 18. AI EXECUTION BOUNDARY

The authoritative execution chain is:

```text
AI Recommendation
        ↓
Capability Resolver
        ↓
Deterministic Policy Engine
        ↓
Action Executor
        ↓
External Adapter / Simulator
```

No LLM may:

- call Razorpay directly;
- modify payment state;
- bypass policy;
- override amount limits;
- bypass capability checks;
- mark a transaction recovered;
- create financial resources directly.

---

# 19. UNKNOWN EXTERNAL OUTCOME

If an external call times out or returns an ambiguous result:

```text
EXECUTING
   ↓
UNKNOWN
   ↓
RECONCILIATION_REQUIRED
   ↓
QUERY EXTERNAL STATE
   ↓
KNOWN OUTCOME
```

Do NOT automatically retry the financial action.

Reconciliation must use the same:

`logical_operation_key`

and existing resource references where available.

---

# 20. IDE IMPLEMENTATION RULE

The 61-step roadmap remains sequential.

For every step:

1. implement only the current step;
2. run its verification commands;
3. inspect the output;
4. fix failures;
5. confirm exit criteria;
6. only then move to the next step.

Do not skip ahead because a later component appears convenient to implement.

Do not redesign an earlier phase during a later step without identifying a verified blocker.

---

# 21. FINAL REAL_TEST ACCEPTANCE FLOW

The REAL_TEST acceptance test is:

```text
1. Controlled test failure event
2. Event ingestion
3. Risk detection
4. Diagnosis
5. Action-conditional decision
6. Capability resolution
7. Policy approval
8. Create Razorpay Payment Link
9. Open Test Mode Payment Link
10. Complete successful test payment
11. Receive payment_link.paid webhook
12. Verify webhook signature
13. Verify payment/link state
14. Attribute recovery
15. Mark operational status RECOVERED
16. Update dashboard
17. Verify audit chain
```

Success criterion:

> The system demonstrates a real Razorpay Test Mode recovery flow with verifiable payment evidence and no real-money movement.

---

# 22. REAL_TEST RATE LIMIT / TEST LIMIT

Razorpay's current Payment Link documentation states that Test Mode allows up to 30 Payment Links per business.

Therefore:

- do not use REAL_TEST for the 50,000-record benchmark;
- use SIMULATION for high-volume evaluation;
- keep REAL_TEST executions intentionally small;
- include the test limit in the verification documentation.

If the external limit changes, the implementation must follow the current official documentation rather than this historical value.

---

# 23. OFFICIAL RAZORPAY VERIFICATION REQUIREMENT

Before implementation of any Razorpay integration:

1. verify the endpoint against current official Razorpay documentation;
2. verify request parameters;
3. verify response fields;
4. verify webhook event names;
5. verify webhook payload structure;
6. verify Test Mode availability;
7. record the verification in the capability matrix.

No undocumented API behavior may be assumed.

---

# 24. FINAL CAPABILITY MATRIX

| Capability | REAL_TEST | SIMULATION | Status |
|---|---:|---:|---|
| Create Payment Link | YES | YES | VERIFIED |
| Payment Link paid webhook | YES | YES | VERIFIED |
| Fetch Payment Link | YES | YES | VERIFIED |
| Fetch Payment | YES | YES | VERIFIED |
| Recovery Message | Internal/demo only | YES | SIMULATION-FIRST |
| Smart Retry | NO unless separately verified | YES | REQUIRES_VERIFICATION |
| Subscription Recovery | Observer / supported native lifecycle only | YES | REQUIRES_EXPLICIT_VERIFICATION |
| Stop | YES | YES | INTERNAL |
| Escalate | YES | YES | INTERNAL |

---

# 25. FINAL ARCHITECTURAL BACKBONE

This remains unchanged:

```text
                    EVENT SOURCES
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
     RAZORPAY         APP EVENTS       SIMULATOR
     WEBHOOKS                         50K+ BATCH
        │                │                │
        ▼                ▼                ▼
              EVENT INGESTION
                     │
              NORMALIZATION
                     │
               DEDUPLICATION
                     │
          STATE TRANSITION SERVICE
                     │
               REVENUE RISK
                     │
                 DIAGNOSIS
                     │
               ACTION SCORING
                     │
              AI RECOMMENDER
                     │
             CAPABILITY RESOLVER
                     │
              POLICY ENGINE
                     │
                EXECUTOR
               /         \
        REAL_TEST       SIMULATION
            │                │
            └───────┬────────┘
                    ▼
              RESULT VERIFY
                    │
             RECONCILIATION
          (UNKNOWN only)
                    │
               ATTRIBUTION
                    │
               MEASUREMENT
                    │
             AUDIT / STOP
                    │
                DASHBOARD
```

---

# 26. FINAL FREEZE CHECKLIST

Before Step 1 begins, confirm:

- [x] Six-phase backbone unchanged.
- [x] 61-step sequence unchanged.
- [x] REAL_TEST and SIMULATION remain strictly separated.
- [x] Payment Link is the primary real executable recovery mechanism.
- [x] `payment_link.paid` is used only after official verification.
- [x] Initial REAL_TEST failure is deterministic and controlled.
- [x] Payment Link creation is not counted as recovered revenue.
- [x] AI cannot execute financial actions directly.
- [x] Capability Resolver precedes Policy Engine.
- [x] Policy Engine is deterministic.
- [x] UNKNOWN triggers reconciliation rather than automatic financial retry.
- [x] Attribution is separate from transaction lifecycle status.
- [x] CONTROL is a cohort, not a lifecycle state.
- [x] Treatment/control comparison is clearly identified as an experimental estimate.
- [x] Monetary values use decimal/minor-unit representation.
- [x] Audit terminology is "tamper-evident hash-chained", not "immutable".
- [x] Policy thresholds are configurable defaults.
- [x] Simulation has 50K+ records and versioned reproducibility metadata.
- [x] No synthetic feature directly leaks the outcome.
- [x] All external Razorpay capabilities are verified before implementation.

---

# 27. AUTHORITY

This document is a correction overlay to the existing `implementation_plan.md`.

After these corrections are incorporated:

**ARCHITECTURE = FROZEN**

Implementation proceeds strictly:

`STEP 1 → VERIFY → STEP 2 → VERIFY → ... → STEP 61`

No further architectural regeneration is required unless a verified external dependency makes a stated capability impossible.

**FINAL STATUS: READY FOR IMPLEMENTATION.**
