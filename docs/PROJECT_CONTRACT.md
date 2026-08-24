# RecoverAI — Project Contract

## 01. Frozen Architectural Commitments
- **Track 03 Alignment:** AI Revenue Recovery system for Razorpay ecosystem.
- **Dual Operational Modes:**
  - `REAL_TEST`: Small-scale Razorpay Test Mode execution using verified APIs (`POST /v1/payment_links`) and `payment_link.paid` webhook verification. Controlled failure injection uses `APP_EVENT: PAYMENT_FAILED`.
  - `SIMULATION`: High-throughput synthetic evaluation on 50,000+ records for statistical validation of recovery strategies.
- **Architecture Flow:** `DETECT` $\rightarrow$ `DIAGNOSE` $\rightarrow$ `DECIDE` $\rightarrow$ `EXECUTE` $\rightarrow$ `VERIFY` $\rightarrow$ `ATTRIBUTE` $\rightarrow$ `MEASURE` $\rightarrow$ `AUDIT`.
- **Non-Bypassable AI Air-Gap:** `LLM Recommender` $\rightarrow$ Structured Validation $\rightarrow$ `CapabilityResolver` $\rightarrow$ `PolicyEngine` $\rightarrow$ `ActionExecutor`.
- **State Machine Isolation:** 4 independent lifecycles (`Transaction`, `Payment`, `Execution`, `Attribution`) governed strictly by `StateTransitionService`.
- **Money Safety:** Monetary amounts strictly represented using `DECIMAL`/`NUMERIC` types. Floating-point types forbidden for financial calculations.
- **Logical Idempotency:** Financial and operational actions governed by `logical_operation_key` (`merchant:tx:cycle:action`) with PostgreSQL unique constraint enforcement.
- **Reconciliation Rule:** `UNKNOWN` external states route to `RECONCILIATION_REQUIRED` without creating duplicate financial operations.
- **Audit Integrity:** Continuous tamper-evident SHA-256 hash chaining anchored to `GENESIS_HASH`.
- **Incremental Value:** Measured as Net Incremental Recovery ($Treatment - Control - Refunds - Costs$). `CONTROL` is a cohort assignment, not a transaction state.
- **No-Silent-Redesign Gate:** Architectural changes require formal human review and approval.
