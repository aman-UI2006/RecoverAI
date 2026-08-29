"""
RecoverAI - Reconciliation Worker Task (Step 22)

Celery / background cron worker executing periodic reconciliation cycles
for pending attempts stuck in UNKNOWN execution state.
"""

import logging
from typing import Any, Dict, Optional
from backend.app.core.database import AsyncSessionLocal
from backend.app.services.reconciliation_engine import ReconciliationEngine
from backend.app.integrations.razorpay_adapter import RazorpayAdapter

logger = logging.getLogger(__name__)


async def run_reconciliation_cycle(
    min_age_seconds: int = 300,
    merchant_id: Optional[str] = None,
    mode: Optional[str] = None,
    razorpay_adapter: Optional[RazorpayAdapter] = None,
) -> Dict[str, Any]:
    """Execute a single reconciliation worker cycle over pending UNKNOWN attempts.

    Args:
        min_age_seconds: Minimum age threshold in seconds for UNKNOWN attempts (defaults to 300s / 5 mins).
        merchant_id: Optional merchant ID filter.
        mode: Optional mode filter ("REAL_TEST" or "SIMULATION").
        razorpay_adapter: Optional custom RazorpayAdapter instance.

    Returns:
        Summary metrics dictionary returned by ReconciliationEngine.
    """
    logger.info(f"Starting reconciliation worker cycle (min_age_seconds={min_age_seconds}, merchant_id={merchant_id}, mode={mode})...")
    engine = ReconciliationEngine(razorpay_adapter=razorpay_adapter)

    async with AsyncSessionLocal() as session:
        try:
            summary = await engine.reconcile_pending_attempts(
                session=session,
                min_age_seconds=min_age_seconds,
                merchant_id=merchant_id,
                mode=mode,
            )
            logger.info(
                f"Reconciliation cycle complete: scanned={summary['total_scanned']}, "
                f"reconciled_success={summary['reconciled_success']}, "
                f"reconciled_failure={summary['reconciled_failure']}, "
                f"pending={summary['pending']}, errors={summary['errors']}"
            )
            return summary
        except Exception as exc:
            logger.error(f"Reconciliation worker cycle encountered an unhandled exception: {exc}")
            raise
