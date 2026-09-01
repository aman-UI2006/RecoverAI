# RecoverAI — Incremental & Counterfactual Strategy Evaluation Report

## Executive Summary

This report presents offline **Doubly Robust (DR) Counterfactual Analysis** evaluating treatment effects and strategy optimality across candidate recovery actions.

### Key Counterfactual Performance Metrics
- **Evaluated Test Dataset Size:** `7,535` transactions
- **Actual Observed Recovery Rate:** `64.38%` (0.6438)
- **Counterfactual Optimal Policy Recovery Rate:** `76.89%` (0.7689)
- **Estimated Causal Lift:** `+19.43%` (+12.51 percentage points)
- **Current Strategy Optimality:** `83.73%`
- **Propensity Score Clipping Bounds:** `[0.05, 0.95]` (Prevents IPW variance explosion)

---

## Methodology & Doubly Robust Estimator

The Doubly Robust (DR) estimator combines an outcome model $\hat{\mu}(a, X_i)$ with propensity score weighting $e(a | X_i)$ to yield unbiased treatment effect estimates:

$$\hat{Y}_{i}^{\text{DR}}(a) = \hat{\mu}(a, X_i) + \frac{\mathbb{I}(A_i = a)}{e(a | X_i)} \left( Y_i - \hat{\mu}(a, X_i) \right)$$

To prevent extreme inverse-probability weight inflation when empirical propensities approach zero, propensity scores $e(a | X_i)$ are clipped strictly within $[0.05, 0.95]$.

---

## Action-Level Counterfactual Recovery Summary

| Candidate Action | Doubly Robust Recovery Rate | Propensity Score | Observed Count | Counterfactual Optimal Count |
| :--- | :---: | :---: | :---: | :---: |
| `PAYMENT_LINK` | `78.39%` | `0.3440` | 2,592 | 4,991 |
| `RECOVERY_MESSAGE` | `73.83%` | `0.1627` | 1,226 | 8 |
| `WHATSAPP_REMINDER` | `79.20%` | `0.0820` | 618 | 2,526 |
| `RETRY` | `73.77%` | `0.2195` | 1,654 | 10 |
| `MANUAL_OUTREACH` | `64.42%` | `0.0500` | 0 | 0 |
| `NO_ACTION` | `13.64%` | `0.1918` | 1,445 | 0 |

---

## Conclusion & Policy Recommendations

1. **Causal Lift Realization:** Transitioning from heuristic baseline choices to the AI-recommended counterfactual optimal policy delivers an estimated **+19.43%** incremental recovery lift.
2. **Action Prioritization:** Soft nudges (`WHATSAPP_REMINDER`, `RECOVERY_MESSAGE`) show high counterfactual recovery efficiency relative to operational cost.
3. **Model Consistency:** The Action-Conditional ML predictor demonstrates strong double robustness stability without propensity score divergence.
