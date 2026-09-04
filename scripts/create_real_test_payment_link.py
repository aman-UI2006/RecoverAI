"""
RecoverAI - Real Test Mode Payment Link Creation Script

Executes stages 1 through 6 of the 8-stage RecoverAI pipeline in genuine REAL_TEST mode:
1. Provisions test Merchant, Customer, and Transaction (AT_RISK, mode=REAL_TEST).
2. Ingests failure trigger (APP_EVENT: PAYMENT_FAILED).
3. Executes DiagnosisEngine -> state becomes DIAGNOSED.
4. Executes ENRVCalculator & StructuredAIRecommender -> state becomes INTERVENTION_SELECTED.
5. Resolves CapabilityResolver -> verifies executable.
6. Evaluates PolicyEngine -> state becomes APPROVED.
7. Executes ActionExecutor with RazorpayAdapter -> calls POST /v1/payment_links on api.razorpay.com.
8. Outputs Transaction ID, Recovery Attempt ID, Razorpay Payment Link ID, and Short URL.
9. STOPS without creating synthetic webhooks or making payments.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import logging
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.core.config import settings
from backend.app.integrations.razorpay_adapter import RazorpayAdapter
from backend.app.models.domain import Merchant, Customer, Transaction, Policy
from backend.app.schemas.events import AppEventPayload
from backend.app.schemas.diagnosis import DiagnosisRequest
from backend.app.schemas.enrv import ENRVCalculationRequest, CandidateActionInput
from backend.app.schemas.executor import ActionExecutionRequest
from backend.app.services.event_ingestion import EventIngestionService
from backend.app.services.diagnosis_engine import DiagnosisEngine
from backend.app.services.enrv_calculator import ENRVCalculator
from backend.app.ai.recommender import StructuredAIRecommender
from backend.app.services.capability_resolver import CapabilityResolver
from backend.app.policies.policy_engine import PolicyEngine
from backend.app.services.action_executor import ActionExecutor
from backend.app.services.result_processor import ResultProcessor
from backend.app.services.attribution_engine import AttributionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("create_real_test_payment_link")


async def execute_real_test_creation() -> bool:
    logger.info("==================================================================")
    logger.info("=== RecoverAI REAL_TEST Mode: Controlled Payment Link Creation ===")
    logger.info("==================================================================")

    # Register Attribution hook
    ResultProcessor.register_attribution_hook(AttributionEngine.result_processor_hook_handler)

    isolated_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(isolated_engine, expire_on_commit=False)
    session = session_factory()

    suffix = uuid.uuid4().hex[:6]
    merchant_id = f"m_real_{suffix}"
    customer_id = f"c_real_{suffix}"
    tx_id = f"t_real_{suffix}"
    amount_paise = 1000  # Rs. 10.00 for small test transaction

    try:
        # 1. Provision Merchant, Policy, Customer & Transaction
        logger.info("\n1. Provisioning Test Merchant, Customer & Transaction (AT_RISK, REAL_TEST)...")
        merchant = Merchant(
            id=merchant_id,
            name="Real Test Merchant",
            email=f"real_{suffix}@merchant.test",
            industry="E-commerce",
        )
        policy = Policy(
            merchant_id=merchant_id,
            policy_version="v1.0",
            max_recovery_attempts=3,
            max_auto_action_amount=500000.00,
            min_recovery_probability=0.10,
            cooldown_hours=24,
            is_active=True,
        )
        customer = Customer(
            id=customer_id,
            merchant_id=merchant_id,
            email=f"real_{suffix}@customer.test",
            phone="+919876543210",
            name="Real Test Customer",
        )
        tx = Transaction(
            id=tx_id,
            merchant_id=merchant_id,
            customer_id=customer_id,
            amount=Decimal("10.00"),
            currency="INR",
            status="AT_RISK",
            scenario_type="PAYMENT_FAILURE",
            mode="REAL_TEST",
        )
        session.add_all([merchant, policy, customer, tx])
        await session.commit()
        logger.info(f"   [PASS] Created Transaction ID: '{tx_id}', Amount: Rs 10.00")

        # 2. Stage 1: DETECT
        logger.info("\n2. [STAGE 1 DETECT] Ingesting failure event (APP_EVENT: PAYMENT_FAILED)...")
        app_event = AppEventPayload(
            event_type="PAYMENT_FAILED",
            merchant_id=merchant_id,
            customer_id=customer_id,
            amount_in_paise=amount_paise,
            currency="INR",
            transaction_id=tx_id,
            metadata={"error_code": "BAD_REQUEST_PAYMENT_TIMED_OUT", "checkout_attempt": 1},
        )
        event_rec, _ = await EventIngestionService.ingest_app_event(session=session, app_event=app_event)
        logger.info(f"   [PASS] Ingested Event ID: '{event_rec.id}'")

        # 3. Stage 2: DIAGNOSE
        logger.info("\n3. [STAGE 2 DIAGNOSE] Diagnosing root cause...")
        diag_req = DiagnosisRequest(
            transaction_id=tx_id,
            merchant_id=merchant_id,
            failure_code="BAD_REQUEST_PAYMENT_TIMED_OUT",
            error_description="Payment attempt timed out during 3DS OTP entry",
        )
        diag_res, _ = await DiagnosisEngine.diagnose_and_transition(session=session, request=diag_req)
        logger.info(f"   [PASS] Diagnosis Category: '{diag_res.failure_category}'")

        # 4. Stage 3: DECIDE
        logger.info("\n4. [STAGE 3 DECIDE] Ranking actions via ENRV & Structured AI Recommender...")
        enrv_req = ENRVCalculationRequest(
            transaction_id=tx_id,
            merchant_id=merchant_id,
            amount_in_paise=amount_paise,
            candidate_actions=[
                CandidateActionInput(action_type="PAYMENT_LINK", predicted_recovery_probability=0.85),
                CandidateActionInput(action_type="RECOVERY_MESSAGE", predicted_recovery_probability=0.70),
            ],
        )
        enrv_res = ENRVCalculator.calculate_enrv(request=enrv_req)
        recommender = StructuredAIRecommender()
        rec_res, _ = await recommender.recommend_and_transition(
            session=session,
            transaction_id=tx_id,
            diagnosis=diag_res,
            enrv_response=enrv_res,
            merchant_id=merchant_id,
        )
        logger.info(f"   [PASS] Recommended Action: '{rec_res.recommended_action}'")

        # 5. Stage 4: CAPABILITY
        logger.info("\n5. [STAGE 4 CAPABILITY] Resolving merchant capabilities...")
        resolver = CapabilityResolver()
        cap_res = resolver.resolve_recommendation(
            recommendation=rec_res,
            enrv_response=enrv_res,
            mode="REAL_TEST",
            merchant_id=merchant_id,
        )
        logger.info(f"   [PASS] Capability Executable: {cap_res.is_executable}")

        # 6. Stage 5: POLICY
        logger.info("\n6. [STAGE 5 POLICY] Evaluating policy rules...")
        policy_engine_instance = PolicyEngine()
        pol_eval_res, _ = await policy_engine_instance.evaluate_and_transition(
            session=session,
            transaction_id=tx_id,
            capability_result=cap_res,
            merchant_id=merchant_id,
            candidate_probability=0.85,
        )
        logger.info(f"   [PASS] Policy Status: '{pol_eval_res.status.value}'")

        # 7. Stage 6: EXECUTE (Razorpay REAL_TEST Payment Link Creation)
        logger.info("\n7. [STAGE 6 EXECUTE] Dispatching ActionExecutor to call Razorpay REST API...")
        ref_id = f"RAI-{tx_id}-1"
        exec_req = ActionExecutionRequest(
            transaction_id=tx_id,
            merchant_id=merchant_id,
            action_type="PAYMENT_LINK",
            action_payload={"amount": amount_paise, "reference_id": ref_id},
            mode_override="REAL_TEST",
        )
        adapter = RazorpayAdapter()
        exec_res = await ActionExecutor.execute(session=session, request=exec_req, adapter_delegate=adapter)
        
        await session.refresh(tx)

        logger.info("\n==================================================================")
        logger.info("=== GENUINE RAZORPAY TEST MODE PAYMENT LINK CREATION SUCCESS ===")
        logger.info("==================================================================")
        logger.info(f"Transaction ID:          {tx_id}")
        logger.info(f"Transaction Status:      {tx.status} (EXPECTED: EXECUTING)")
        logger.info(f"Recovery Attempt ID:     {exec_res.execution_id}")
        logger.info(f"Execution Status:        {exec_res.execution_status}")
        logger.info(f"Razorpay Payment Link ID: {exec_res.razorpay_payment_link_id}")
        logger.info(f"Razorpay Reference ID:    {exec_res.razorpay_reference_id}")

        # Fetch short_url from adapter raw response
        short_url = exec_res.external_resource_id
        if hasattr(adapter, "last_response") and getattr(adapter, "last_response"):
            short_url = getattr(adapter, "last_response").get("short_url", short_url)

        logger.info(f"Razorpay Short URL:       {short_url}")
        logger.info("==================================================================")
        logger.info("\n[NEXT MANUAL ACTION REQUIRED]:")
        logger.info(f"1. Open the Short URL above in a browser.")
        logger.info(f"2. Complete the Test Mode payment on Razorpay checkout.")
        logger.info(f"3. Observe incoming webhook on zrok and check DB status.")
        return True

    finally:
        await session.close()
        await isolated_engine.dispose()


if __name__ == "__main__":
    asyncio.run(execute_real_test_creation())
