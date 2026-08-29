# RecoverAI — Project Status

- **Current Step:** Step 4 (Ground Truth and Evaluation Split) — VERIFIED
- **Last Verified Step:** Step 4 (Ground Truth and Evaluation Split)
- **Current Status:** VERIFIED / READY_FOR_STEP_5
- **Last Known Good Commit:** `333cde3` (`step-04-verified: deterministic customer-group dataset splitting`)
- **Blocking Issue:** None
- **Environment Status:** Python 3.13.7, Node v25.1.0, npm 11.6.2, Virtualenv `venv` provisioned, PostgreSQL 16 active on port 5432.
- **LLM Provider Status:** Groq API (`groq/compound-mini`) LIVE AUTHENTICATED & VERIFIED (Approved via DEC-006).
- **Dataset Split Status:** 50,000 synthetic transactions partitioned deterministically (seed 42, DEC-007) into `data/train.parquet` (35,110 rows, 70.22%), `data/val.parquet` (7,355 rows, 14.71%), `data/test.parquet` (7,535 rows, 15.07%). Hard zero customer overlap and deterministic internal ordering (`created_at` ASC, `transaction_id` ASC) verified.
- **Test Status:** 54/54 tests passing (`pytest backend/tests`).
- **Dependencies Status:** Full backend (`requirements.txt`) and frontend (`package.json`) dependencies installed and validated.
- **Database Status:** VERIFIED against PostgreSQL 16 (`recoverai_db`). All 13 core tables verified.
