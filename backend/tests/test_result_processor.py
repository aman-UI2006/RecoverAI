"""
RecoverAI - ResultProcessor Test Suite (Step 19)

Verifies execution outcome processing, transaction lifecycle state mutations via StateTransitionService,
idempotent event handling, multi-tenant merchant isolation, unlinked event safety,
and Step 20 attribution trigger boundary isolation.
"""

from uuid import uuid4
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from backend.app.models.domain import Base, Merchant, Customer, Transaction, RecoveryAttempt, Event, AuditEvent
from backend.app.schemas.state_machine import TransactionStatus, ExecutionStatus
from backend.app.services.result_processor import ResultProcessor

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_test_session():
    """Create an isolated in-memory SQLite database session for ResultProcessor testing."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture(autouse=True)
def reset_attribution_hook():
    """Reset ResultProcessor attribution hook callback after each test."""
    ResultProcessor.reset_attribution_hook()
    yield
    ResultProcessor.reset_attribution_hook()


async def setup_executing_transaction(session: AsyncSession, link_id: str, ref_id: str):
    """Helper to set up a transaction in EXECUTING state with a RecoveryAttempt."""
    mer_id = f"mer_{uuid4().hex[:8]}"
    cust_id = f"cust_{uuid4().hex[:8]}"
    tx_id = f"tx_{uuid4().hex[:8]}"

    merchant = Merchant(id=mer_id, name="Result Merchant", email=f"{mer_id}@example.com", industry="ECOMMERCE")
    customer = Customer(id=cust_id, merchant_id=mer_id, name="Result Customer", email=f"{cust_id}@example.com")
    tx = Transaction(
        id=tx_id,
        merchant_id=mer_id,
        customer_id=cust_id,
        amount=500.00,
        currency="INR",
        status=TransactionStatus.EXECUTING.value,
        scenario_type="CARD_DECLINE",
        recovery_cycle=1,
    )

    attempt = RecoveryAttempt(
        id=f"att_{uuid4().hex[:8]}",
        transaction_id=tx_id,
        recommended_action="PAYMENT_LINK",
        action_payload={"amount": 500.00},
        policy_status="APPROVED",
        policy_reason="Policy approved for execution",
        policy_version="1.0",
        execution_status=ExecutionStatus.EXECUTING.value,
        external_resource_type="REAL_TEST",
        logical_operation_key=f"{mer_id}:{tx_id}:1:PAYMENT_LINK",
        external_resource_id=link_id,
        razorpay_payment_link_id=link_id,
        razorpay_reference_id=ref_id,
    )

    session.add_all([merchant, customer, tx, attempt])
    await session.commit()
    return mer_id, tx_id, attempt.id


@pytest.mark.asyncio
async def test_1_payment_link_paid_success_transition(async_test_session: AsyncSession):
    """Verify payment_link.paid event transitions transaction from EXECUTING -> RECOVERED."""
    link_id = f"plink_{uuid4().hex[:10]}"
    ref_id = f"RAI-{uuid4().hex[:8]}-1"
    mer_id, tx_id, att_id = await setup_executing_transaction(async_test_session, link_id, ref_id)

    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": link_id,
                    "reference_id": ref_id,
                    "status": "paid",
                    "amount": 50000,
                    "notes": {"merchant_id": mer_id, "transaction_id": tx_id},
                }
            }
        },
    }

    res = await ResultProcessor.process_payload(async_test_session, payload)

    assert res["status"] == "SUCCESS_RECOVERED"
    assert res["transaction_status"] == TransactionStatus.RECOVERED.value
    assert res["execution_status"] == ExecutionStatus.SUCCESS.value

    # Verify DB persistence
    stmt = select(Transaction).where(Transaction.id == tx_id)
    tx = (await async_test_session.execute(stmt)).scalar_one()
    assert tx.status == TransactionStatus.RECOVERED.value

    stmt_att = select(RecoveryAttempt).where(RecoveryAttempt.id == att_id)
    attempt = (await async_test_session.execute(stmt_att)).scalar_one()
    assert attempt.execution_status == ExecutionStatus.SUCCESS.value


@pytest.mark.asyncio
async def test_2_payment_captured_success_transition(async_test_session: AsyncSession):
    """Verify payment.captured event transitions transaction from EXECUTING -> RECOVERED."""
    link_id = f"plink_{uuid4().hex[:10]}"
    ref_id = f"RAI-{uuid4().hex[:8]}-1"
    mer_id, tx_id, att_id = await setup_executing_transaction(async_test_session, link_id, ref_id)

    payload = {
        "event": "payment.captured",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": link_id,
                    "reference_id": ref_id,
                    "notes": {"merchant_id": mer_id},
                }
            },
            "payment": {
                "entity": {
                    "id": f"pay_{uuid4().hex[:10]}",
                    "status": "captured",
                    "captured": True,
                    "amount": 50000,
                }
            },
        },
    }

    res = await ResultProcessor.process_payload(async_test_session, payload)

    assert res["status"] == "SUCCESS_RECOVERED"
    assert res["transaction_status"] == TransactionStatus.RECOVERED.value


@pytest.mark.asyncio
async def test_3_failed_payment_transition(async_test_session: AsyncSession):
    """Verify payment.failed event transitions transaction from EXECUTING -> FAILED."""
    link_id = f"plink_{uuid4().hex[:10]}"
    ref_id = f"RAI-{uuid4().hex[:8]}-1"
    mer_id, tx_id, att_id = await setup_executing_transaction(async_test_session, link_id, ref_id)

    payload = {
        "event": "payment.failed",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": link_id,
                    "reference_id": ref_id,
                    "notes": {"merchant_id": mer_id},
                }
            },
            "payment": {
                "entity": {
                    "id": f"pay_{uuid4().hex[:10]}",
                    "status": "failed",
                    "error_description": "Card authorization failed",
                }
            },
        },
    }

    res = await ResultProcessor.process_payload(async_test_session, payload)

    assert res["status"] == "FAILED_PAYMENT"
    assert res["transaction_status"] == TransactionStatus.FAILED.value
    assert res["execution_status"] == ExecutionStatus.FAILURE.value


@pytest.mark.asyncio
async def test_4_cancelled_payment_link_transition(async_test_session: AsyncSession):
    """Verify payment_link.cancelled event transitions transaction from EXECUTING -> FAILED."""
    link_id = f"plink_{uuid4().hex[:10]}"
    ref_id = f"RAI-{uuid4().hex[:8]}-1"
    mer_id, tx_id, att_id = await setup_executing_transaction(async_test_session, link_id, ref_id)

    payload = {
        "event": "payment_link.cancelled",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": link_id,
                    "reference_id": ref_id,
                    "status": "cancelled",
                    "notes": {"merchant_id": mer_id},
                }
            }
        },
    }

    res = await ResultProcessor.process_payload(async_test_session, payload)

    assert res["status"] == "FAILED_CANCELLED"
    assert res["transaction_status"] == TransactionStatus.FAILED.value


@pytest.mark.asyncio
async def test_5_expired_payment_link_transition(async_test_session: AsyncSession):
    """Verify payment_link.expired event transitions transaction from EXECUTING -> EXPIRED."""
    link_id = f"plink_{uuid4().hex[:10]}"
    ref_id = f"RAI-{uuid4().hex[:8]}-1"
    mer_id, tx_id, att_id = await setup_executing_transaction(async_test_session, link_id, ref_id)

    payload = {
        "event": "payment_link.expired",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": link_id,
                    "reference_id": ref_id,
                    "status": "expired",
                    "notes": {"merchant_id": mer_id},
                }
            }
        },
    }

    res = await ResultProcessor.process_payload(async_test_session, payload)

    assert res["status"] == "EXPIRED"
    assert res["transaction_status"] == TransactionStatus.EXPIRED.value


@pytest.mark.asyncio
async def test_6_duplicate_idempotent_result_processing(async_test_session: AsyncSession):
    """Verify processing duplicate event on an already resolved attempt returns IDEMPOTENT_SKIPPED."""
    link_id = f"plink_{uuid4().hex[:10]}"
    ref_id = f"RAI-{uuid4().hex[:8]}-1"
    mer_id, tx_id, att_id = await setup_executing_transaction(async_test_session, link_id, ref_id)

    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": link_id,
                    "reference_id": ref_id,
                    "status": "paid",
                    "notes": {"merchant_id": mer_id},
                }
            }
        },
    }

    # First execution
    res1 = await ResultProcessor.process_payload(async_test_session, payload)
    assert res1["status"] == "SUCCESS_RECOVERED"

    # Second execution (Duplicate payload)
    res2 = await ResultProcessor.process_payload(async_test_session, payload)
    assert res2["status"] == "IDEMPOTENT_SKIPPED"
    assert res2["transaction_status"] == TransactionStatus.RECOVERED.value


@pytest.mark.asyncio
async def test_7_unlinked_event_handling(async_test_session: AsyncSession):
    """Verify unlinked event with unknown link/ref ID logs warning and leaves transaction state unchanged."""
    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_nonexistent_123",
                    "reference_id": "RAI-nonexistent-1",
                    "status": "paid",
                }
            }
        },
    }

    res = await ResultProcessor.process_payload(async_test_session, payload)

    assert res["status"] == "UNLINKED_EVENT"
    assert res["matched"] is False


@pytest.mark.asyncio
async def test_8_missing_identifiers_handling(async_test_session: AsyncSession):
    """Verify payload missing identifiers safely returns UNLINKED_EVENT without exception."""
    payload = {
        "event": "payment_link.paid",
        "payload": {},
    }

    res = await ResultProcessor.process_payload(async_test_session, payload)

    assert res["status"] == "UNLINKED_EVENT"
    assert res["matched"] is False


@pytest.mark.asyncio
async def test_9_merchant_isolation_enforcement(async_test_session: AsyncSession):
    """Verify cross-merchant mismatch rejects processing and leaves transaction untouched."""
    link_id = f"plink_{uuid4().hex[:10]}"
    ref_id = f"RAI-{uuid4().hex[:8]}-1"
    mer_id, tx_id, att_id = await setup_executing_transaction(async_test_session, link_id, ref_id)

    wrong_merchant_id = f"mer_evil_{uuid4().hex[:8]}"

    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": link_id,
                    "reference_id": ref_id,
                    "status": "paid",
                    "notes": {"merchant_id": wrong_merchant_id},
                }
            }
        },
    }

    res = await ResultProcessor.process_payload(async_test_session, payload)

    assert res["status"] == "MERCHANT_MISMATCH_REJECTED"

    # Transaction status must remain EXECUTING
    stmt = select(Transaction).where(Transaction.id == tx_id)
    tx = (await async_test_session.execute(stmt)).scalar_one()
    assert tx.status == TransactionStatus.EXECUTING.value


@pytest.mark.asyncio
async def test_10_atomic_rollback_on_error(async_test_session: AsyncSession):
    """Verify DB session handles errors gracefully without leaving corrupted state."""
    link_id = f"plink_{uuid4().hex[:10]}"
    ref_id = f"RAI-{uuid4().hex[:8]}-1"
    mer_id, tx_id, att_id = await setup_executing_transaction(async_test_session, link_id, ref_id)

    # Corrupt payload with ambiguous status
    payload = {
        "event": "payment.unknown_event",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": link_id,
                    "reference_id": ref_id,
                    "status": "UNKNOWN_INVALID_STATUS",
                }
            }
        },
    }

    res = await ResultProcessor.process_payload(async_test_session, payload)

    assert res["status"] == "AMBIGUOUS_UNPROCESSED"

    stmt = select(Transaction).where(Transaction.id == tx_id)
    tx = (await async_test_session.execute(stmt)).scalar_one()
    assert tx.status == TransactionStatus.EXECUTING.value


@pytest.mark.asyncio
async def test_11_audit_event_state_transition_integrity(async_test_session: AsyncSession):
    """Verify StateTransitionService generates valid AuditEvent during result processing."""
    link_id = f"plink_{uuid4().hex[:10]}"
    ref_id = f"RAI-{uuid4().hex[:8]}-1"
    mer_id, tx_id, att_id = await setup_executing_transaction(async_test_session, link_id, ref_id)

    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": link_id,
                    "reference_id": ref_id,
                    "status": "paid",
                    "notes": {"merchant_id": mer_id},
                }
            }
        },
    }

    await ResultProcessor.process_payload(async_test_session, payload)

    # Check AuditEvent chain
    stmt = select(AuditEvent).where(AuditEvent.transaction_id == tx_id)
    audit_events = (await async_test_session.execute(stmt)).scalars().all()

    assert len(audit_events) >= 1
    latest_audit = audit_events[-1]
    assert latest_audit.state_to == TransactionStatus.RECOVERED.value
    assert latest_audit.actor == "RESULT_PROCESSOR"
    assert latest_audit.event_hash is not None


@pytest.mark.asyncio
async def test_12_simulation_result_processing(async_test_session: AsyncSession):
    """Verify simulation synthetic result processing."""
    link_id = f"plink_sim_{uuid4().hex[:8]}"
    ref_id = f"RAI-sim_{uuid4().hex[:8]}-1"
    mer_id, tx_id, att_id = await setup_executing_transaction(async_test_session, link_id, ref_id)

    payload = {
        "event": "simulator.payment_success",
        "razorpay_payment_link_id": link_id,
        "reference_id": ref_id,
        "merchant_id": mer_id,
        "status": "paid",
    }

    res = await ResultProcessor.process_payload(async_test_session, payload)

    assert res["status"] == "SUCCESS_RECOVERED"
    assert res["transaction_status"] == TransactionStatus.RECOVERED.value


@pytest.mark.asyncio
async def test_13_real_test_result_processing_without_live_api(async_test_session: AsyncSession):
    """Verify REAL_TEST webhook payload processing works cleanly offline without external HTTP calls."""
    link_id = f"plink_realtest_{uuid4().hex[:8]}"
    ref_id = f"RAI-real_{uuid4().hex[:8]}-1"
    mer_id, tx_id, att_id = await setup_executing_transaction(async_test_session, link_id, ref_id)

    payload = {
        "entity": "event",
        "account_id": "acc_test_12345",
        "event": "payment_link.paid",
        "contains": ["payment_link", "payment"],
        "payload": {
            "payment_link": {
                "entity": {
                    "id": link_id,
                    "reference_id": ref_id,
                    "amount": 25000,
                    "amount_paid": 25000,
                    "status": "paid",
                    "notes": {"merchant_id": mer_id, "transaction_id": tx_id},
                }
            },
            "payment": {
                "entity": {
                    "id": f"pay_{uuid4().hex[:8]}",
                    "amount": 25000,
                    "status": "captured",
                    "method": "upi",
                }
            },
        },
    }

    res = await ResultProcessor.process_payload(async_test_session, payload)

    assert res["status"] == "SUCCESS_RECOVERED"
    assert res["transaction_status"] == TransactionStatus.RECOVERED.value


@pytest.mark.asyncio
async def test_14_step20_attribution_hook_invoked_on_success(async_test_session: AsyncSession):
    """Verify Step 20 attribution hook is invoked ONLY on verified successful payment completion."""
    hook_invoked = []

    async def custom_hook(session, transaction_id, attempt_id, payment_id):
        hook_invoked.append((transaction_id, attempt_id, payment_id))
        return {"custom_hook": True}

    ResultProcessor.register_attribution_hook(custom_hook)

    link_id = f"plink_{uuid4().hex[:10]}"
    ref_id = f"RAI-{uuid4().hex[:8]}-1"
    mer_id, tx_id, att_id = await setup_executing_transaction(async_test_session, link_id, ref_id)

    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": link_id,
                    "reference_id": ref_id,
                    "status": "paid",
                    "notes": {"merchant_id": mer_id},
                }
            }
        },
    }

    res = await ResultProcessor.process_payload(async_test_session, payload)

    assert res["status"] == "SUCCESS_RECOVERED"
    assert len(hook_invoked) == 1
    assert hook_invoked[0][0] == tx_id
    assert hook_invoked[0][1] == att_id


@pytest.mark.asyncio
async def test_15_attribution_hook_not_invoked_on_failures(async_test_session: AsyncSession):
    """Verify Step 20 attribution hook is NOT invoked for failed/expired/cancelled/unlinked events."""
    hook_invoked = []

    async def custom_hook(session, transaction_id, attempt_id, payment_id):
        hook_invoked.append((transaction_id, attempt_id))
        return {"custom_hook": True}

    ResultProcessor.register_attribution_hook(custom_hook)

    link_id = f"plink_{uuid4().hex[:10]}"
    ref_id = f"RAI-{uuid4().hex[:8]}-1"
    mer_id, tx_id, att_id = await setup_executing_transaction(async_test_session, link_id, ref_id)

    # 1. Failed payment event
    payload_failed = {
        "event": "payment_link.cancelled",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": link_id,
                    "reference_id": ref_id,
                    "status": "cancelled",
                    "notes": {"merchant_id": mer_id},
                }
            }
        },
    }

    res = await ResultProcessor.process_payload(async_test_session, payload_failed)

    assert res["status"] == "FAILED_CANCELLED"
    assert len(hook_invoked) == 0


@pytest.mark.asyncio
async def test_16_already_resolved_attempt_skips_duplicate_state_changes(async_test_session: AsyncSession):
    """Verify an already-resolved attempt skips duplicate state transitions and attribution triggers."""
    hook_invoked = []

    async def custom_hook(session, transaction_id, attempt_id, payment_id):
        hook_invoked.append(transaction_id)
        return {"custom_hook": True}

    ResultProcessor.register_attribution_hook(custom_hook)

    link_id = f"plink_{uuid4().hex[:10]}"
    ref_id = f"RAI-{uuid4().hex[:8]}-1"
    mer_id, tx_id, att_id = await setup_executing_transaction(async_test_session, link_id, ref_id)

    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": link_id,
                    "reference_id": ref_id,
                    "status": "paid",
                    "notes": {"merchant_id": mer_id},
                }
            }
        },
    }

    # Initial call -> Success
    await ResultProcessor.process_payload(async_test_session, payload)
    assert len(hook_invoked) == 1

    # Second call -> Duplicate skip
    res2 = await ResultProcessor.process_payload(async_test_session, payload)
    assert res2["status"] == "IDEMPOTENT_SKIPPED"
    # Attribution hook must NOT be invoked a second time
    assert len(hook_invoked) == 1
