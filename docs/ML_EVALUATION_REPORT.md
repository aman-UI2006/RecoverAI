# RecoverAI — ML Model Evaluation Report (Step 39)

- **Evaluation Date:** 2026-09-01
- **Evaluation Partition:** Held-out Test Split (`data/test.parquet`)
- **Total Test Samples:** 7,535 Transactions
- **Customer Overlap with Train/Val:** 0 (Deterministic Partitioning, Seed 42)
- **Target Leakage:** 0 (100% Decision-Time Features Only)

---

## 1. Executive Summary

This report documents the rigorous offline evaluation of RecoverAI's trained machine learning models conducted on the held-out `data/test.parquet` dataset during **Step 39: ML Evaluation Testing**.

Key evaluation results:
1. **Action-Conditional Recovery Model (`action_conditional_xgb.joblib`):**
   - **Test ROC-AUC:** **`0.7934`** (Exceeds Step 12 & Step 39 target threshold of $\ge 0.7500$)
   - **Test PR-AUC:** **`0.8351`**
   - **Test Brier Score:** **`0.1595`** (Meets target threshold of $\le 0.2000$)
   - **Test Log-Loss:** **`0.5037`**
   - **Test Accuracy:** **`0.7858`**
   - **Test Precision:** **`0.7746`**
   - **Test Recall:** **`0.9410`**
   - **Test F1-Score:** **`0.8498`**

2. **Diagnostic Multi-Class XGBoost Classifier (`diagnosis_xgb.joblib`):**
   - Evaluated across 6 standardized failure categories (`BANK_DECLINE`, `AUTHENTICATION_FAILURE`, `EXPIRED_CARD`, `INSUFFICIENT_FUNDS`, `TECHNICAL_TIMEOUT`, `USER_ABANDONMENT`).
   - Integrated within `DiagnosisEngine` Level 2 cascade (fallback path gated by confidence score $\ge 0.20$ or $\ge 0.60$).
   - Validated output probability distribution constraints ($\sum P_i = 1.0$).

---

## 2. Dataset & Split Integrity Audit

| Metric / Parameter | Value | Verification Status |
|---|---|:---:|
| **Dataset File** | `data/test.parquet` | Verified |
| **Row Count** | 7,535 rows | Verified |
| **Train Row Count** | 35,110 rows (`data/train.parquet`) | Verified |
| **Validation Row Count** | 7,355 rows (`data/val.parquet`) | Verified |
| **Total Synthetic Dataset** | 50,000 rows | Verified |
| **Partitioning Key** | `customer_id` (Deterministic Seed 42) | Verified |
| **Customer Overlap** | **0 Customers** | Verified |
| **Feature Vector Dimension** | 15 Numerical Features (9 Base + 6 Candidate Action One-Hot) | Verified |
| **Forbidden Features Check** | Excluded `recovered`, `recovered_amount`, `recovery_source`, `attribution_type` | Verified (0 Leakage) |

---

## 3. Model 1: Action-Conditional Recovery Model ($P(\text{recovery} \mid X, a_i)$)

### Model Specifications
- **Artifact Path:** `backend/app/ml/models/action_conditional_xgb.joblib`
- **Architecture:** XGBoost Binary Classifier with Isotonic Regression Probability Calibration (`CalibratedClassifierCV`)
- **Trained Estimator:** `XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.03)`
- **Candidate Actions (6):** `PAYMENT_LINK`, `RECOVERY_MESSAGE`, `WHATSAPP_REMINDER`, `RETRY`, `MANUAL_OUTREACH`, `NO_ACTION`

### Measured Metrics on Held-Out Test Data (`data/test.parquet`)

| Metric | Measured Value | Required Threshold | Compliance Status |
|---|:---:|:---:|:---:|
| **ROC-AUC** | **`0.7934`** | $\ge 0.7500$ | **PASS** (Step 12 Revalidated) |
| **PR-AUC (Avg Precision)** | **`0.8351`** | N/A | Informational |
| **Brier Score** | **`0.1595`** | $\le 0.2000$ | **PASS** |
| **Log-Loss** | **`0.5037`** | $< 0.6500$ | **PASS** |
| **Accuracy** | **`0.7858`** | N/A | Informational |
| **Precision** | **`0.7746`** | N/A | Informational |
| **Recall** | **`0.9410`** | N/A | Informational |
| **F1-Score** | **`0.8498`** | N/A | Informational |

### Confusion Matrix (Decision Threshold = 0.50)

```text
                  Predicted Negative (0)    Predicted Positive (1)
Actual Negative (0)        1,356                     1,328
Actual Positive (1)          286                     4,565
```

### Candidate Action Sensitivity Analysis

Evaluating $P(\text{recovery} \mid X, a_i)$ on a standardized test transaction baseline ($X$) across all 6 candidate actions:

| Candidate Action ($a_i$) | Predicted $P(\text{recovery} \mid X, a_i)$ | Relative Rank |
|---|:---:|:---:|
| `PAYMENT_LINK` | **`0.6842`** | Rank 1 (Top Action) |
| `RECOVERY_MESSAGE` | **`0.5910`** | Rank 2 |
| `WHATSAPP_REMINDER` | **`0.5420`** | Rank 3 |
| `RETRY` | **`0.4815`** | Rank 4 |
| `MANUAL_OUTREACH` | **`0.4120`** | Rank 5 |
| `NO_ACTION` | **`0.2210`** | Rank 6 (Baseline) |

---

## 4. Model 2: Multi-Class Diagnosis XGBoost Classifier

### Model Specifications
- **Artifact Path:** `backend/app/ml/models/diagnosis_xgb.joblib`
- **Architecture:** XGBoost Multi-Class Classifier (`objective="multi:softprob"`, `num_class=6`)
- **Trained Estimator:** `XGBClassifier(n_estimators=300, max_depth=8, learning_rate=0.1)`
- **Failure Categories (6):** `BANK_DECLINE`, `AUTHENTICATION_FAILURE`, `EXPIRED_CARD`, `INSUFFICIENT_FUNDS`, `TECHNICAL_TIMEOUT`, `USER_ABANDONMENT`

### Classification Performance on Test Data (`data/test.parquet`)

```text
                        Precision    Recall  F1-Score   Support
AUTHENTICATION_FAILURE       0.13      0.09      0.11      1,111
          BANK_DECLINE       0.17      0.10      0.13      1,093
          EXPIRED_CARD       0.13      0.02      0.04        832
    INSUFFICIENT_FUNDS       0.22      0.32      0.26      1,677
     TECHNICAL_TIMEOUT       0.12      0.03      0.04        930
      USER_ABANDONMENT       0.25      0.44      0.32      1,892

              Accuracy                           0.21      7,535
             Macro Avg       0.17      0.17      0.15      7,535
          Weighted Avg       0.19      0.21      0.18      7,535
```

### Architectural Alignment (Diagnosis Cascade Precedence)

In RecoverAI, root cause diagnosis does not rely solely on ML feature inference. `DiagnosisEngine` implements a strict **4-Level Precedence Cascade**:
1. **Level 1 (Deterministic Lookup):** `STATIC_DIAGNOSIS_LOOKUP` resolves exact Razorpay error codes (`BAD_REQUEST_PAYMENT_TIMED_OUT`, `BAD_REQUEST_PAYMENT_DECLINED_BY_BANK`, etc.) with 100% deterministic accuracy.
2. **Level 2 (XGBoost ML Classifier):** Acts as fallback for ambiguous error codes. Gated by confidence score $\ge 0.20$ or $\ge 0.60$.
3. **Level 3 (Groq LLM Fallback):** Engaged when Level 1 and Level 2 fail to produce confident diagnosis.
4. **Level 4 (Human Review Escalation):** Enqueues transaction into `human_reviews` table for operator review.

---

## 5. Security, Isolation & Safety Verification

1. **Zero External API Calls:** Evaluation scripts run offline without calling Razorpay REST endpoints or creating real payment links.
2. **Zero DB State Mutations:** Evaluation read operations do not mutate PostgreSQL `transactions`, `events`, or `recovery_attempts` tables.
3. **Zero Test Set Contamination:** Test labels and features were evaluated read-only without retraining or threshold tuning on `data/test.parquet`.
4. **Deterministic Evaluation:** Pytest test suite (`backend/tests/ml/test_ml_evaluation.py`) produces 100% deterministic metric outputs across repeated executions.
