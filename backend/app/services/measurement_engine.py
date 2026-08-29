"""
RecoverAI - Control/Treatment Measurement Engine (Step 21)

Calculates incremental recovery rates, net recovered revenue, and ROI metrics
comparing Treatment cohorts (RecoverAI interventions) against Baseline Control cohorts.
Enforces Decimal financial precision, multi-tenant isolation, mode separation (REAL_TEST vs SIMULATION),
zero transaction state mutation, and persistence into evaluation_runs.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.domain import (
    Transaction,
    RecoveryAttempt,
    RecoveryAttribution,
    EvaluationRun,
)
from backend.app.schemas.analytics import (
    CohortMetrics,
    MeasurementRequest,
    MeasurementResponse,
)

logger = logging.getLogger(__name__)


class MeasurementEngine:
    """Measurement Engine for calculating incremental recovery lift and net business ROI."""

    @staticmethod
    def _current_utc_time() -> datetime:
        """Helper to return naive UTC datetime consistent with database models."""
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @classmethod
    def calculate_cohort_lift(
        cls,
        treatment_eligible_count: int,
        treatment_eligible_amount: Decimal,
        treatment_recovered_count: int,
        treatment_recovered_amount: Decimal,
        treatment_refunds: Decimal,
        treatment_costs: Decimal,
        control_eligible_count: int,
        control_eligible_amount: Decimal,
        control_recovered_count: int,
        control_recovered_amount: Decimal,
        control_refunds: Decimal = Decimal("0.00"),
        control_costs: Decimal = Decimal("0.00"),
    ) -> Dict[str, Any]:
        """Pure calculation function for treatment vs control metrics using Decimal arithmetic.

        Formulas:
            7.1 Treatment Recovery Rate = Treatment Recovered Count / Treatment Eligible Count
            7.2 Control Recovery Rate = Control Recovered Count / Control Eligible Count
            7.3 Incremental Recovery Rate = Treatment Rate - Control Rate
            7.4 Net Incremental Revenue = (Incremental Rate * Treatment Eligible Amount) - Treatment Refunds - Treatment Costs

        Returns:
            Dictionary containing computed rates and amounts.
        """
        # 1. Treatment Rates & Monies (Decimal safe)
        if treatment_eligible_count > 0:
            treatment_rate = Decimal(treatment_recovered_count) / Decimal(treatment_eligible_count)
        else:
            treatment_rate = Decimal("0.0000")

        if treatment_eligible_amount > Decimal("0.00"):
            treatment_amount_rate = treatment_recovered_amount / treatment_eligible_amount
        else:
            treatment_amount_rate = Decimal("0.0000")

        # 2. Control Rates & Monies (Decimal safe)
        if control_eligible_count > 0:
            control_rate = Decimal(control_recovered_count) / Decimal(control_eligible_count)
        else:
            control_rate = Decimal("0.0000")

        if control_eligible_amount > Decimal("0.00"):
            control_amount_rate = control_recovered_amount / control_eligible_amount
        else:
            control_amount_rate = Decimal("0.0000")

        # 3. Incremental Recovery Rate (Subtask 7.3)
        incremental_rate = treatment_rate - control_rate

        # 4. Estimated Incremental Recovered Amount
        # (Incremental Rate * Treatment Eligible Amount)
        estimated_incremental_recovered = (incremental_rate * treatment_eligible_amount).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # 5. Net Incremental Revenue (Subtask 7.4)
        # Net Incremental Revenue = Estimated Incremental Recovered - Refunds - Costs
        net_incremental_revenue = (
            estimated_incremental_recovered - treatment_refunds - treatment_costs
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return {
            "treatment_recovery_rate": float(treatment_rate),
            "treatment_amount_rate": float(treatment_amount_rate),
            "control_recovery_rate": float(control_rate),
            "control_amount_rate": float(control_amount_rate),
            "incremental_recovery_rate": float(incremental_rate),
            "treatment_recovered_amount": treatment_recovered_amount,
            "control_recovered_amount": control_recovered_amount,
            "estimated_incremental_recovered_amount": estimated_incremental_recovered,
            "net_incremental_revenue": net_incremental_revenue,
        }

    @classmethod
    async def evaluate_measurement(
        cls,
        session: AsyncSession,
        request: MeasurementRequest,
    ) -> MeasurementResponse:
        """Evaluate and report control vs treatment measurement from database.

        Args:
            session: Active AsyncSession instance.
            request: MeasurementRequest specifying mode, merchant filter, and metadata.

        Returns:
            MeasurementResponse containing computed lift and persisted run record ID if enabled.
        """
        now = cls._current_utc_time()
        mode_filter = request.mode or "SIMULATION"

        # Construct base Transaction filters
        tx_filters = [Transaction.mode == mode_filter]
        if request.merchant_id:
            tx_filters.append(Transaction.merchant_id == request.merchant_id)
        if request.start_time:
            tx_filters.append(Transaction.created_at >= request.start_time)
        if request.end_time:
            tx_filters.append(Transaction.created_at <= request.end_time)

        # Fetch all candidate transactions matching window & tenant
        stmt_tx = select(Transaction).where(and_(*tx_filters))
        tx_rows = (await session.execute(stmt_tx)).scalars().all()

        treatment_eligible_count = 0
        treatment_eligible_amount = Decimal("0.00")
        treatment_recovered_count = 0
        treatment_recovered_amount = Decimal("0.00")
        treatment_refunds = Decimal("0.00")
        treatment_costs = Decimal("0.00")

        control_eligible_count = 0
        control_eligible_amount = Decimal("0.00")
        control_recovered_count = 0
        control_recovered_amount = Decimal("0.00")
        control_refunds = Decimal("0.00")
        control_costs = Decimal("0.00")

        for tx in tx_rows:
            tx_amount = Decimal(str(tx.amount))

            # Query RecoveryAttempt for treatment identification
            stmt_attempt = select(RecoveryAttempt).where(RecoveryAttempt.transaction_id == tx.id)
            attempts = (await session.execute(stmt_attempt)).scalars().all()

            # Query RecoveryAttribution for outcome verification
            stmt_attr = select(RecoveryAttribution).where(RecoveryAttribution.transaction_id == tx.id)
            attributions = (await session.execute(stmt_attr)).scalars().all()

            is_treatment = len(attempts) > 0

            if is_treatment:
                treatment_eligible_count += 1
                treatment_eligible_amount += tx_amount

                # Check if recovered via attribution
                for attr in attributions:
                    if attr.attribution_status in ("ATTRIBUTED", "NATURAL_RECOVERY"):
                        treatment_recovered_count += 1
                        treatment_recovered_amount += Decimal(str(attr.recovered_amount))
                        treatment_refunds += Decimal(str(attr.refunded_amount))
                        break
            else:
                control_eligible_count += 1
                control_eligible_amount += tx_amount

                # Check if recovered in control
                if tx.status == "RECOVERED":
                    control_recovered_count += 1
                    control_recovered_amount += tx_amount

        # Execute pure math calculation
        calc = cls.calculate_cohort_lift(
            treatment_eligible_count=treatment_eligible_count,
            treatment_eligible_amount=treatment_eligible_amount,
            treatment_recovered_count=treatment_recovered_count,
            treatment_recovered_amount=treatment_recovered_amount,
            treatment_refunds=treatment_refunds,
            treatment_costs=treatment_costs,
            control_eligible_count=control_eligible_count,
            control_eligible_amount=control_eligible_amount,
            control_recovered_count=control_recovered_count,
            control_recovered_amount=control_recovered_amount,
            control_refunds=control_refunds,
            control_costs=control_costs,
        )

        treatment_metrics = CohortMetrics(
            total_eligible_count=treatment_eligible_count,
            total_eligible_amount=float(treatment_eligible_amount),
            recovered_count=treatment_recovered_count,
            recovered_amount=float(treatment_recovered_amount),
            recovery_rate=calc["treatment_recovery_rate"],
            refunded_amount=float(treatment_refunds),
            intervention_cost=float(treatment_costs),
        )

        control_metrics = CohortMetrics(
            total_eligible_count=control_eligible_count,
            total_eligible_amount=float(control_eligible_amount),
            recovered_count=control_recovered_count,
            recovered_amount=float(control_recovered_amount),
            recovery_rate=calc["control_recovery_rate"],
            refunded_amount=float(control_refunds),
            intervention_cost=float(control_costs),
        )

        total_size = request.dataset_size or (treatment_eligible_count + control_eligible_count)
        total_risk_amount = treatment_eligible_amount + control_eligible_amount

        summary = {
            "treatment_amount_rate": calc["treatment_amount_rate"],
            "control_amount_rate": calc["control_amount_rate"],
            "treatment_eligible_count": treatment_eligible_count,
            "control_eligible_count": control_eligible_count,
            "treatment_recovered_count": treatment_recovered_count,
            "control_recovered_count": control_recovered_count,
            "net_incremental_revenue": float(calc["net_incremental_revenue"]),
            "estimated_incremental_recovered_amount": float(calc["estimated_incremental_recovered_amount"]),
        }

        eval_run_id: Optional[str] = None

        if request.persist_evaluation_run:
            eval_run = EvaluationRun(
                run_name=request.run_name,
                dataset_version=request.dataset_version,
                dataset_size=total_size,
                random_seed=request.random_seed,
                model_version=request.model_version,
                feature_version=request.feature_version,
                policy_version=request.policy_version,
                configuration_version=request.configuration_version,
                code_commit_sha=request.code_commit_sha,
                mode=mode_filter,
                revenue_at_risk=float(total_risk_amount),
                baseline_recovered_amount=float(control_recovered_amount),
                recoverai_gross_recovered_amount=float(treatment_recovered_amount),
                incremental_recovered_amount=float(calc["estimated_incremental_recovered_amount"]),
                baseline_recovery_rate=calc["control_recovery_rate"],
                recoverai_recovery_rate=calc["treatment_recovery_rate"],
                summary_metrics=summary,
                created_at=now,
            )

            session.add(eval_run)
            await session.commit()
            await session.refresh(eval_run)
            eval_run_id = eval_run.id
            logger.info(f"Persisted EvaluationRun '{eval_run.id}' for run '{request.run_name}'.")

        return MeasurementResponse(
            evaluation_run_id=eval_run_id,
            run_name=request.run_name,
            mode=mode_filter,
            merchant_id=request.merchant_id,
            treatment_metrics=treatment_metrics,
            control_metrics=control_metrics,
            treatment_recovery_rate=calc["treatment_recovery_rate"],
            control_recovery_rate=calc["control_recovery_rate"],
            incremental_recovery_rate=calc["incremental_recovery_rate"],
            treatment_recovered_amount=float(treatment_recovered_amount),
            control_recovered_amount=float(control_recovered_amount),
            estimated_incremental_recovered_amount=float(calc["estimated_incremental_recovered_amount"]),
            net_incremental_revenue=float(calc["net_incremental_revenue"]),
            summary_metrics=summary,
            created_at=now,
        )
