# RecoverAI — Error Log

| Error ID | Step | Component | Symptoms | Exact Error | Root Cause | Fix | Regression Tests | Status |
|---|---|---|---|---|---|---|---|---|
| ERR-000 | 0 | Environment | Git repo missing | `fatal: not a git repository` | Working directory `d:\Razorpay\New folder` not initialized as Git repo | Run `git init` and commit baseline | Baseline status check | RESOLVED |
| ERR-001 | 5 | Ingestion | Body `event_id` payload assumption | Razorpay webhook event ID assumed in JSON body payload | Official Razorpay webhooks pass event ID via HTTP header `X-Razorpay-Event-Id`, not JSON body | Extracted `X-Razorpay-Event-Id` header in FastAPI router and passed as authoritative event ID | `test_3_conflicting_body_field_cannot_override_header_event_id`, `test_7_idempotency_duplicate_event_id_handling` | RESOLVED |
