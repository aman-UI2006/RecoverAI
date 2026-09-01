# RecoverAI — Innovation & Strategy Optimization Documentation

## Multi-Objective Action-Conditional Expected Net Recovery Value ($ENRV$) Optimization

### 1. Executive Summary

Standard recovery engines optimize purely for single-transaction recovery probability $P(\text{recovery} \mid X, a_i)$ or immediate gross recovery revenue. However, aggressive intervention channels (such as repeated automated retries, agent phone calls, or intrusive payment demands) can introduce customer friction, increasing customer churn risk—especially among high Lifetime Value ($LTV$) merchants and enterprise subscribers.

Step 43 introduces **Multi-Objective Strategy Optimization** into the `StrategyOptimizerService`, elevating basic cost-deduction ENRV to long-term merchant profitability optimization.

---

### 2. Mathematical Formulation

#### Base Expected Net Recovery Value ($ENRV_{\text{base}}$)
$$\text{ENRV}_{\text{base}}(a_i) = P(R \mid X, a_i) \cdot \text{Amount} - C_{\text{intervention}}(a_i) - C_{\text{operational}}(a_i) - C_{\text{refund}}(a_i)$$

Where:
- $P(R \mid X, a_i)$: Action-conditional recovery probability.
- $\text{Amount}$: Eligible transaction amount in minor units (paise).
- $C_{\text{intervention}}, C_{\text{operational}}, C_{\text{refund}}$: Direct execution and operational costs.

#### Customer Churn Risk Penalty ($\text{Penalty}_{\text{churn}}$)
$$\text{Penalty}_{\text{churn}}(a_i) = \text{ChurnRisk} \cdot \text{LTV}_{\text{paise}} \cdot w_{\text{aggressiveness}}(a_i)$$

Where:
- $\text{ChurnRisk} \in [0.0, 1.0]$: Customer churn risk score derived from historical friction and transaction failure frequency.
- $\text{LTV}_{\text{paise}}$: Estimated customer lifetime value in minor monetary units (paise).
- $w_{\text{aggressiveness}}(a_i) \in [0.0, 1.0]$: Predefined channel aggressiveness/friction coefficient.

#### Channel Aggressiveness Weights ($w_{\text{aggressiveness}}$)
| Action Identifier | Aggressiveness Weight ($w$) | Description / Friction Level |
|---|---|---|
| `MANUAL_OUTREACH` | **1.0** | Agent outreach / phone call (Maximum friction) |
| `RETRY` | **0.8** | Gateway retry attempt (High friction) |
| `PAYMENT_LINK` | **0.4** | Payment Link generation (Moderate friction) |
| `WHATSAPP_REMINDER` | **0.2** | WhatsApp notification (Low friction / soft nudge) |
| `RECOVERY_MESSAGE` | **0.1** | Email / In-app message (Very low friction / soft nudge) |
| `NO_ACTION` | **0.0** | Passive observation (Zero friction) |

#### Multi-Objective Optimized ENRV ($\text{ENRV}_{\text{optimized}}$)
$$\text{ENRV}_{\text{optimized}}(a_i) = \text{ENRV}_{\text{base}}(a_i) - \text{Penalty}_{\text{churn}}(a_i)$$

---

### 3. Decision Boundary & Soft Nudge Prioritization

- **High-LTV / High-Churn Customers:** When $\text{ChurnRisk} \cdot \text{LTV}$ is large, aggressive actions like `MANUAL_OUTREACH` and `RETRY` incur steep monetary penalties. The system dynamically re-ranks candidate actions to prioritize **Soft Nudges** (`WHATSAPP_REMINDER`, `RECOVERY_MESSAGE`), protecting long-term subscriber revenue.
- **Low-LTV / Neutral-Churn Customers:** When $\text{LTV}$ or $\text{ChurnRisk}$ is zero/unspecified, $\text{Penalty}_{\text{churn}} = 0$, causing $\text{ENRV}_{\text{optimized}} = \text{ENRV}_{\text{base}}$, seamlessly preserving baseline financial return maximization.
