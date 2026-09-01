"""
RecoverAI - Step 48: Customer Communication Engine Unit & API Tests

Verifies tone selector categorization (Empathetic, Urgent, Informative, Direct),
PII masking redaction, dynamic Payment Link placeholder insertion, execution boundary
enforcement (REAL_TEST content generation vs SIMULATION modeling), and FastAPI endpoint handling.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.ai.communication_engine import CommunicationEngine
from backend.app.schemas.communication import CommunicationRequest
from backend.app.main import app

client = TestClient(app)


def test_tone_selection():
    """Verify tone selection logic across scenarios, failure codes, and customer segments."""
    # Empathetic for subscriptions
    tone1 = CommunicationEngine.select_tone(scenario_type="SUBSCRIPTION_LAPSE")
    assert tone1 == "Empathetic"

    # Urgent for insufficient funds or high amount
    tone2 = CommunicationEngine.select_tone(scenario_type="INSUFFICIENT_FUNDS", amount_rupees=500.0)
    assert tone2 == "Urgent"

    tone3 = CommunicationEngine.select_tone(scenario_type="TECHNICAL_GATEWAY", amount_rupees=12000.0)
    assert tone3 == "Urgent"

    # Direct for VIP/Enterprise
    tone4 = CommunicationEngine.select_tone(scenario_type="TECHNICAL_GATEWAY", customer_segment="VIP")
    assert tone4 == "Direct"

    # Informative for standard technical failure
    tone5 = CommunicationEngine.select_tone(scenario_type="GATEWAY_TIMEOUT")
    assert tone5 == "Informative"


def test_pii_masking():
    """Verify regex-based PII redaction for email, phone, and card numbers."""
    raw_text = "Contact john.doe@example.com or call +91 9876543210 regarding card 4111222233334444."
    masked = CommunicationEngine.mask_pii(raw_text)

    assert "john.doe@example.com" not in masked
    assert "@example.com" in masked
    assert "9876543210" not in masked
    assert "98****3210" in masked
    assert "4111222233334444" not in masked
    assert "**** **** **** 4444" in masked


def test_communication_generation_simulation_mode():
    """Verify SIMULATION mode models delivery status and open probability."""
    engine = CommunicationEngine()
    req = CommunicationRequest(
        customer_id="cust_123",
        scenario_type="SUBSCRIPTION_LAPSE",
        amount_rupees=1499.00,
        payment_link="https://rzp.io/i/test_link_123",
        mode="SIMULATION",
    )

    res = engine.generate_communication(req)
    assert res.tone == "Empathetic"
    assert "https://rzp.io/i/test_link_123" in res.raw_message_text
    assert res.execution_mode == "SIMULATION"
    assert res.is_sent is True
    assert res.simulated_delivery_status == "DELIVERED"
    assert res.simulated_open_probability is not None


def test_communication_generation_real_test_mode():
    """Verify REAL_TEST execution boundary generates content ONLY without external dispatch."""
    engine = CommunicationEngine()
    req = CommunicationRequest(
        customer_id="cust_123",
        scenario_type="INSUFFICIENT_FUNDS",
        amount_rupees=2500.00,
        payment_link="https://rzp.io/i/real_link_456",
        mode="REAL_TEST",
    )

    res = engine.generate_communication(req)
    assert res.tone == "Urgent"
    assert "https://rzp.io/i/real_link_456" in res.raw_message_text
    assert res.execution_mode == "REAL_TEST"
    assert res.is_sent is False
    assert res.simulated_delivery_status == "NOT_SENT_REAL_TEST_CONTENT_ONLY"
    assert res.simulated_open_probability is None


def test_communication_api_endpoint():
    """Verify POST /api/v1/communication/generate REST endpoint returns valid response."""
    payload = {
        "customer_id": "cust_999",
        "scenario_type": "GATEWAY_TIMEOUT",
        "amount_rupees": 500.0,
        "payment_link": "https://rzp.io/i/api_demo",
        "preferred_channel": "WHATSAPP",
        "mode": "SIMULATION",
    }

    response = client.post("/api/v1/communication/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["tone"] == "Informative"
    assert data["channel"] == "WHATSAPP"
    assert "https://rzp.io/i/api_demo" in data["raw_message_text"]
    assert data["execution_mode"] == "SIMULATION"
