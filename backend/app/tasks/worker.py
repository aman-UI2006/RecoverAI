"""
RecoverAI - Celery Background Task Worker Entry Point (Step 51)

Configures the Celery application instance and defines background worker tasks
for async reconciliation cycles and background processing.
"""

import asyncio
import logging
from celery import Celery

from backend.app.core.config import settings
from backend.app.workers.reconciliation_worker import run_reconciliation_cycle

logger = logging.getLogger(__name__)

# Initialize Celery app instance
celery_app = Celery(
    "recoverai_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="backend.app.tasks.worker.run_reconciliation_task")
def run_reconciliation_task(min_age_seconds: int = 300, merchant_id: str = None, mode: str = None):
    """Celery background task wrapper executing an async reconciliation cycle."""
    logger.info("Executing Celery background task: run_reconciliation_task...")
    return asyncio.run(run_reconciliation_cycle(
        min_age_seconds=min_age_seconds,
        merchant_id=merchant_id,
        mode=mode,
    ))
