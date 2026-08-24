# RecoverAI — Dependency Map

```mermaid
graph TD
    Client[Web Dashboard / Webhook Caller] -->|REST / Webhook| FastAPI[FastAPI Backend]
    FastAPI -->|State Machine & Transactions| DB[(PostgreSQL 13 Tables)]
    FastAPI -->|Async Tasks & Queues| Redis[(Redis / Celery)]
    FastAPI -->|Risk Detection| RiskEngine[RevenueRiskEngine]
    FastAPI -->|Root Cause Diagnosis| DiagnosisEngine[DiagnosisEngine]
    FastAPI -->|ENRV Action Ranking| ActionML[Action-Conditional ML]
    ActionML -->|AI Recommendation| Capability[CapabilityResolver]
    Capability -->|Verified Capabilities| Policy[PolicyEngine]
    Policy -->|Approved Execution| Executor[ActionExecutor]
    Executor -->|POST /v1/payment_links| Razorpay[Razorpay Test Mode API]
    Razorpay -->|payment_link.paid| WebhookHandler[Webhook Ingestion]
    WebhookHandler -->|Verify & Mutate| StateService[StateTransitionService]
    StateService -->|Attribution & Lift| AttributionEngine[Attribution & Measurement]
    FastAPI -->|Append Event| AuditService[AuditTrailService]
    AuditService -->|SHA-256 Hash Chain| DB
```

## Component Interdependencies
1. **Database:** Postgres 16+ serving as single source of truth for 13 relational tables.
2. **State Transition Service:** Centralized gatekeeper for all state mutations using `SELECT ... FOR UPDATE` locking.
3. **AI Air-Gap:** `Diagnosis/ML` outputs recommendation $\rightarrow$ `CapabilityResolver` $\rightarrow$ `PolicyEngine` $\rightarrow$ `ActionExecutor`.
4. **Audit Trail:** Asynchronous & synchronous hash chaining (`GENESIS_HASH` $\rightarrow$ linked SHA-256 records).
5. **Razorpay Client:** Wrapper for `POST /v1/payment_links` and HMAC SHA-256 webhook validation.
