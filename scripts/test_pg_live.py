import asyncio
import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, delete

from backend.app.core.database import Base
from backend.app.models import (
    Merchant, Customer, Transaction, Event, DecisionContext,
    RecoveryActionScore, Diagnosis, Policy, RecoveryAttempt,
    RecoveryAttribution, AuditEvent, EvaluationRun, HumanReview
)

PG_ASYNC_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/recoverai_db"

async def test_live_postgresql():
    engine = create_async_engine(PG_ASYNC_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    run_id = str(uuid.uuid4())[:8]

    async with session_factory() as session:
        print("\n--- 1. Insert Merchant ---")
        merchant = Merchant(
            name=f"Live PG Merchant {run_id}",
            email=f"livepg_{run_id}@merchant.com",
            industry="Fintech"
        )
        session.add(merchant)
        await session.commit()
        await session.refresh(merchant)
        merchant_id = merchant.id
        print(f"[PASS] Merchant inserted with ID: {merchant_id}")

        print("\n--- 2. Insert Customer ---")
        customer = Customer(
            merchant_id=merchant_id,
            email=f"livepg_customer_{run_id}@example.com",
            name="Jane Doe",
            historical_transaction_count=10
        )
        session.add(customer)
        await session.commit()
        await session.refresh(customer)
        customer_id = customer.id
        print(f"[PASS] Customer inserted with ID: {customer_id}")

        print("\n--- 3. Insert Transaction & Check NUMERIC(12,2) ---")
        tx = Transaction(
            merchant_id=merchant_id,
            customer_id=customer_id,
            amount=Decimal("49999.99"),
            currency="INR",
            status="AT_RISK",
            scenario_type="SUBSCRIPTION_FAILURE",
            mode="SIMULATION"
        )
        session.add(tx)
        await session.commit()
        await session.refresh(tx)
        tx_id = tx.id
        assert tx.amount == Decimal("49999.99")
        print(f"[PASS] Transaction inserted with ID: {tx_id}, Amount: {tx.amount}")

        print("\n--- 4. Insert Event ---")
        idempotency_key = f"pg_idempotent_key_{run_id}"
        event = Event(
            transaction_id=tx_id,
            event_type="subscription.charged_failed",
            event_source="RAZORPAY_WEBHOOK",
            payload={"event": "subscription.charged_failed", "amount": 4999999},
            idempotency_key=idempotency_key
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)
        event_id = event.id
        print(f"[PASS] Event inserted with ID: {event_id}")

        print("\n--- 5. Duplicate Idempotency Key Must Fail ---")
        event_dup = Event(
            transaction_id=tx_id,
            event_type="subscription.charged_failed",
            event_source="RAZORPAY_WEBHOOK",
            payload={"event": "duplicate"},
            idempotency_key=idempotency_key
        )
        session.add(event_dup)
        try:
            await session.commit()
            assert False, "Should have raised IntegrityError!"
        except IntegrityError:
            await session.rollback()
            print("[PASS] Duplicate idempotency_key failed with IntegrityError as expected!")

        print("\n--- 6. Insert RecoveryAttempt & Duplicate logical_operation_key Must Fail ---")
        op_key = f"{merchant_id}:{tx_id}:1:SUBSCRIPTION_RECOVERY"
        attempt1 = RecoveryAttempt(
            transaction_id=tx_id,
            logical_operation_key=op_key,
            recommended_action="SUBSCRIPTION_RECOVERY",
            action_payload={"method": "charge_retry"},
            policy_status="APPROVED",
            policy_version="v1.0",
            execution_status="PENDING",
            external_resource_type="RAZORPAY_SUBSCRIPTION"
        )
        session.add(attempt1)
        await session.commit()
        await session.refresh(attempt1)
        attempt_id = attempt1.id

        attempt_dup = RecoveryAttempt(
            transaction_id=tx_id,
            logical_operation_key=op_key,
            recommended_action="SUBSCRIPTION_RECOVERY",
            action_payload={"method": "charge_retry"},
            policy_status="APPROVED",
            policy_version="v1.0",
            execution_status="PENDING",
            external_resource_type="RAZORPAY_SUBSCRIPTION"
        )
        session.add(attempt_dup)
        try:
            await session.commit()
            assert False, "Should have raised IntegrityError!"
        except IntegrityError:
            await session.rollback()
            print("[PASS] Duplicate logical_operation_key failed with IntegrityError as expected!")

        print("\n--- 7. Foreign Key Violation Must Fail ---")
        invalid_tx = Transaction(
            merchant_id="non_existent_merchant_id_999",
            customer_id=customer_id,
            amount=Decimal("100.00"),
            status="CREATED",
            scenario_type="PAYMENT_FAILURE"
        )
        session.add(invalid_tx)
        try:
            await session.commit()
            assert False, "Should have raised IntegrityError!"
        except IntegrityError:
            await session.rollback()
            print("[PASS] Foreign key violation failed with IntegrityError as expected!")

        print("\n--- 8. Audit Record Can Be Stored ---")
        audit = AuditEvent(
            transaction_id=tx_id,
            event_type="STATE_TRANSITION",
            actor="SYSTEM",
            state_from="CREATED",
            state_to="AT_RISK",
            details={"source": "pg_live_test"},
            previous_hash="0000000000000000000000000000000000000000000000000000000000000000",
            event_hash=f"hash_{run_id}_1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff"[:64]
        )
        session.add(audit)
        await session.commit()
        await session.refresh(audit)
        audit_id = audit.id
        print(f"[PASS] AuditEvent inserted with Hash: {audit.event_hash}")

        # Cleanup test records safely
        print("\nCleaning up test records...")
        await session.execute(delete(AuditEvent).where(AuditEvent.id == audit_id))
        await session.execute(delete(RecoveryAttempt).where(RecoveryAttempt.id == attempt_id))
        await session.execute(delete(Event).where(Event.id == event_id))
        await session.execute(delete(Transaction).where(Transaction.id == tx_id))
        await session.execute(delete(Customer).where(Customer.id == customer_id))
        await session.execute(delete(Merchant).where(Merchant.id == merchant_id))
        await session.commit()
        print("[PASS] Cleanup completed safely.")

    await engine.dispose()
    print("\nALL LIVE POSTGRESQL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_live_postgresql())
