# RecoverAI — Decision Log

| ID | Date | Decision | Reason | Alternatives Considered | Status |
|---|---|---|---|---|---|
| DEC-001 | 2026-08-24 | Frozen 61-Step Roadmap & Modular Monolith | Ensures deterministic execution and avoids over-engineering for Buildathon. | Microservices, Kafka event mesh | APPROVED |
| DEC-002 | 2026-08-24 | REAL_TEST Execution Boundary | `POST /v1/payment_links` is the sole verified Razorpay recovery API endpoint. Controlled failure trigger uses `APP_EVENT: PAYMENT_FAILED`. | Unverified charge retries | APPROVED |
| DEC-003 | 2026-08-24 | Tamper-Evident SHA-256 Audit Trail | Cryptographic hash chaining anchored to `GENESIS_HASH` provides verifiable integrity without misleading immutability claims. | Append-only DB without hashing | APPROVED |
| DEC-004 | 2026-08-24 | Safe Execution Protocol Adoption | Adopting strict single-step verification, control documents, and git rollback safety. | Ad-hoc step execution | APPROVED |
| DEC-005 | 2026-08-26 | LLM Provider Selection: Groq API | Project owner selected Groq API (Free tier) with model `llama-3.3-70b-versatile`. Groq operates behind existing AI service abstraction with strict safety boundaries. | OpenAI API | APPROVED |
