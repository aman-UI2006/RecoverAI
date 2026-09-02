"""
RecoverAI - Step 54 Focused System Verification Tests

Validates the full system-wide end-to-end verification pipeline:
1. Synthetic dataset evaluation metrics verification.
2. End-to-end 8-stage lifecycle pipeline (DETECT -> DIAGNOSE -> DECIDE -> CAPABILITY -> POLICY -> EXECUTE -> VERIFY -> ATTRIBUTE -> MEASURE -> AUDIT).
3. Replay protection & idempotency verification.
4. Multi-tenant security isolation & HMAC signature rejection verification.
5. System verification report generation (docs/SYSTEM_VERIFICATION_REPORT.md).
"""

import pytest
import pytest_asyncio
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.core.config import settings
from scripts.full_system_verification import run_full_system_verification, generate_verification_report


@pytest_asyncio.fixture
async def isolated_session():
    """Provides a fresh AsyncSession bound to a NullPool engine to prevent event loop connection pollution."""
    test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_step54_full_system_verification_sweep(isolated_session):
    """Verify that run_full_system_verification executes cleanly end-to-end."""
    success, results = await run_full_system_verification(session=isolated_session)
    assert success is True
    assert results["dataset_verification"] is True
    assert results["idempotency_verification"] is True
    assert results["security_isolation_verification"] is True
    assert results["measurement_verification"] is True
    assert len(results["scenarios_simulation"]) == 4
    assert len(results["scenarios_real_test"]) == 4


@pytest.mark.asyncio
async def test_step54_report_generation():
    """Verify that system verification report generates valid markdown content."""
    mock_results = {
        "dataset_verification": True,
        "mode_classifications": {"REAL_TEST": "SIMULATION — VERIFIED (Fallback)"},
    }
    report_md = generate_verification_report(mock_results)
    assert "# RecoverAI — System Verification Report (Step 54)" in report_md
    assert "1. DETECT" in report_md
    assert "VERIFIED SUCCESSFUL" in report_md

    report_path = Path(__file__).parent.parent.parent / "docs" / "SYSTEM_VERIFICATION_REPORT.md"
    assert report_path.exists()
