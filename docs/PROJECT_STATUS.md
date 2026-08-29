# RecoverAI — Project Status

- **Current Step:** Step 12 (Action-Conditional ML) — NOT VERIFIED (EXIT CRITERION BLOCKED)
- **Last Verified Step:** Step 11 (Diagnosis Engine) — VERIFIED (Commit `6fa828a`)
- **Current Status:** STEP 11 VERIFIED / STEP 12 BLOCKED ON EXIT CRITERION
- **Last Known Good Commit:** Pending Step 11 remediation commit
- **Blocking Issue:** ERR-004: Step 12 measured test ROC-AUC (0.7421) is below frozen plan requirement (>= 0.75). Proven Bayes Oracle upper bound on current synthetic dataset is 0.7454.
- **Environment Status:** Python 3.13.7, Node v25.1.0, npm 11.6.2, Virtualenv `venv` provisioned, PostgreSQL 16 active on port 5432.
- **LLM Provider Status:** Groq API (`groq/compound-mini`) LIVE AUTHENTICATED & VERIFIED (Approved via DEC-006).
- **Dataset Split Status:** 50,000 synthetic transactions partitioned deterministically (seed 42, DEC-007) into `data/train.parquet` (35,110 rows, 70.22%), `data/val.parquet` (7,355 rows, 14.71%), `data/test.parquet` (7,535 rows, 15.07%). Hard zero customer overlap and deterministic internal ordering (`created_at` ASC, `transaction_id` ASC) verified.
- **Event Ingestion & Normalization Status:** FastAPI Webhook Router (`/webhooks/razorpay`, `/app-event`, `/simulator-event`), EventNormalizerService, canonical NormalizedEvent schemas, PostgreSQL ACID boundary deduplication, and Redis fast-path caching with graceful fallback implemented.
- **State Transition Service Status:** Centralized StateTransitionService (`backend/app/services/state_transition_service.py`), StateMachine schemas & transition matrix (`backend/app/schemas/state_machine.py`), SELECT ... FOR UPDATE row-locking, and SHA-256 tamper-evident audit event hash chaining implemented and verified.
- **Revenue Risk Engine Status:** RevenueRiskEngine (`backend/app/services/revenue_risk_engine.py`) and RiskAssessment schemas (`backend/app/schemas/risk_assessment.py`) implemented and verified. DET-001 multi-tenant merchant verification timing remediated.
- **Feature Engineering Status:** FeatureExtractor (`backend/app/ml/feature_extractor.py`) and Feature schemas (`backend/app/schemas/features.py`) implemented and verified. Transforms raw transaction context into validated, cold-start safe numerical feature vectors with zero target leakage and zero PII.
- **ENRV Foundation Status:** ENRVCalculator (`backend/app/services/enrv_calculator.py`) and ENRV schemas (`backend/app/schemas/enrv.py`) implemented and verified. Evaluates and ranks candidate recovery actions by ENRV(a_i) = P(R | X, a_i) * AmountInPaise - InterventionCost - OperationalCost - RefundCost. Persists action scores to `decision_contexts` and `recovery_action_scores` with multi-tenant isolation.
- **Diagnosis Engine Status:** DiagnosisEngine (`backend/app/services/diagnosis_engine.py`), MLDiagnosisClassifier (`backend/app/ml/diagnosis_classifier.py`), and Diagnosis schemas (`backend/app/schemas/diagnosis.py`) implemented and verified. Classifies root cause across 4 precedence levels (Rules -> ML Classifier -> Groq LLM Fallback -> Human Review Fallback), sanitizes PII, mutates transaction status to DIAGNOSED via StateTransitionService, and logs AuditEvent.
- **Action-Conditional ML Status:** ActionConditionalPredictor (`backend/app/ml/action_conditional_model.py`), training script (`scripts/train_action_conditional_model.py`), and model artifact (`backend/app/ml/models/action_conditional_xgb.joblib`) implemented and verified. Predicts calibrated P(recovery | X, a_i) across 6 candidate actions with zero target leakage, zero PII, and advisory-only execution.
- **Test Status:** 118/118 tests passing (`pytest backend/tests`).
- **Dependencies Status:** Full backend (`requirements.txt`) and frontend (`package.json`) dependencies installed and validated.
- **Database Status:** VERIFIED against PostgreSQL 16 (`recoverai_db`). All 13 core tables verified.
