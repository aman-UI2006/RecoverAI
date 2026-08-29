"""
RecoverAI - Synthetic Dataset Generator (Step 3)

Generates a deterministic synthetic dataset of 50,000+ transaction records
for offline ML model training, policy simulation, and evaluation.
Adheres strictly to DEC-007, DEC-008, and DEC-009.
"""

import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

# Scenario Constants
SCENARIO_PAYMENT_FAILURE = "PAYMENT_FAILURE"
SCENARIO_CHECKOUT_ABANDONMENT = "CHECKOUT_ABANDONMENT"
SCENARIO_SUBSCRIPTION_FAILURE = "SUBSCRIPTION_FAILURE"
SCENARIO_OVERDUE_RECEIVABLE = "OVERDUE_RECEIVABLE"

SCENARIOS = [
    SCENARIO_PAYMENT_FAILURE,
    SCENARIO_CHECKOUT_ABANDONMENT,
    SCENARIO_SUBSCRIPTION_FAILURE,
    SCENARIO_OVERDUE_RECEIVABLE,
]

# Action Catalog Constants
ACTION_PAYMENT_LINK = "PAYMENT_LINK"
ACTION_RECOVERY_MESSAGE = "RECOVERY_MESSAGE"
ACTION_RETRY = "RETRY"
ACTION_SUBSCRIPTION_RECOVERY = "SUBSCRIPTION_RECOVERY"
ACTION_STOP = "STOP"

# DEC-008 Historical Action Policy (Approved Synthetic Simulation Assumptions)
HISTORICAL_ACTION_POLICIES: Dict[str, List[Tuple[str, float]]] = {
    SCENARIO_PAYMENT_FAILURE: [
        (ACTION_PAYMENT_LINK, 0.45),
        (ACTION_RETRY, 0.35),
        (ACTION_STOP, 0.20),
    ],
    SCENARIO_CHECKOUT_ABANDONMENT: [
        (ACTION_RECOVERY_MESSAGE, 0.50),
        (ACTION_PAYMENT_LINK, 0.30),
        (ACTION_STOP, 0.20),
    ],
    SCENARIO_SUBSCRIPTION_FAILURE: [
        (ACTION_SUBSCRIPTION_RECOVERY, 0.40),
        (ACTION_RETRY, 0.40),
        (ACTION_STOP, 0.20),
    ],
    SCENARIO_OVERDUE_RECEIVABLE: [
        (ACTION_PAYMENT_LINK, 0.60),
        (ACTION_RECOVERY_MESSAGE, 0.25),
        (ACTION_STOP, 0.15),
    ],
}

# Scenario Weights
SCENARIO_WEIGHTS = [0.40, 0.25, 0.20, 0.15]

# Payment Methods & Checkout Devices
PAYMENT_METHODS = ["CARD", "UPI", "NETBANKING", "NACH", "WALLET"]
CHECKOUT_DEVICES = ["MOBILE_APP", "DESKTOP_WEB", "MOBILE_WEB"]

# Decline Codes mapping per scenario
DECLINE_CODES_MAP = {
    SCENARIO_PAYMENT_FAILURE: [
        ("INSUFFICIENT_FUNDS", 0.40),
        ("AUTHENTICATION_FAILED", 0.30),
        ("GATEWAY_TIMEOUT", 0.15),
        ("NETWORK_ERROR", 0.15),
    ],
    SCENARIO_CHECKOUT_ABANDONMENT: [
        ("NONE", 1.00),
    ],
    SCENARIO_SUBSCRIPTION_FAILURE: [
        ("CARD_EXPIRED", 0.50),
        ("INSUFFICIENT_FUNDS", 0.35),
        ("AUTHENTICATION_FAILED", 0.15),
    ],
    SCENARIO_OVERDUE_RECEIVABLE: [
        ("NONE", 1.00),
    ],
}


def _sigmoid(x: float) -> float:
    """Standard sigmoid activation function."""
    return 1.0 / (1.0 + math.exp(-x))


class SyntheticDatasetGenerator:
    """
    Deterministic Synthetic Dataset Generator for RecoverAI.
    Generates 50,000+ records anchored to random_seed=42.
    """

    def __init__(self, random_seed: int = 42) -> None:
        self.random_seed = random_seed
        self._set_seed(random_seed)

    def _set_seed(self, seed: int) -> None:
        """Lock all random seeds deterministically."""
        random.seed(seed)
        np.random.seed(seed)

    def generate_merchants_and_customers(
        self, num_merchants: int = 10, num_customers: int = 5000
    ) -> Tuple[List[str], List[str]]:
        """Generates pools of deterministic Merchant and Customer UUIDs."""
        # Reset seed before generating pools
        merchant_rng = random.Random(self.random_seed + 100)
        customer_rng = random.Random(self.random_seed + 200)

        merchants = [str(uuid.UUID(int=merchant_rng.getrandbits(128))) for _ in range(num_merchants)]
        customers = [str(uuid.UUID(int=customer_rng.getrandbits(128))) for _ in range(num_customers)]
        return merchants, customers

    def generate_dataset(self, num_records: int = 50000) -> pd.DataFrame:
        """
        Generates deterministic synthetic transaction dataset.

        Args:
            num_records: Total number of records to generate (default: 50,000).

        Returns:
            pd.DataFrame: Deterministic synthetic dataset matching schema requirements.
        """
        self._set_seed(self.random_seed)

        merchants, customers = self.generate_merchants_and_customers()

        start_time = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        time_span_seconds = int(90 * 84600)  # 90 days

        # Generate scenario assignments based on scenario weights
        scenario_indices = np.random.choice(
            len(SCENARIOS), size=num_records, p=SCENARIO_WEIGHTS
        )

        records: List[Dict[str, Any]] = []

        # Deterministic UUID generation stream
        tx_uuid_rng = random.Random(self.random_seed + 300)

        for i in range(num_records):
            scenario = SCENARIOS[scenario_indices[i]]

            # Transaction ID
            tx_id = str(uuid.UUID(int=tx_uuid_rng.getrandbits(128)))

            # Merchant & Customer selection
            merchant_id = random.choice(merchants)
            customer_id = random.choice(customers)

            # Created timestamp
            offset_seconds = random.randint(0, time_span_seconds)
            created_at = start_time + timedelta(seconds=offset_seconds)

            # Amount generation (log-normal, centered around ~₹2,500)
            # Bound between ₹100.00 (10,000 paise) and ₹500,000.00 (50,000,000 paise)
            raw_amount = float(np.random.lognormal(mean=7.8, sigma=1.0))
            amount_rupees = round(max(100.0, min(500000.0, raw_amount)), 2)
            amount_in_paise = int(round(amount_rupees * 100))

            # Payment method & checkout device
            payment_method = random.choice(PAYMENT_METHODS)
            checkout_device = random.choice(CHECKOUT_DEVICES)

            # Decline code selection based on scenario
            decline_choices, decline_probs = zip(*DECLINE_CODES_MAP[scenario])
            decline_code = np.random.choice(decline_choices, p=decline_probs)

            # Customer attributes
            customer_tenure_days = int(random.randint(0, 3650))
            historical_success_rate = round(float(np.random.beta(a=8, b=2)), 4)
            historical_success_rate = max(0.0, min(1.0, historical_success_rate))

            prior_failed_attempts = int(min(10, np.random.poisson(lam=0.8)))

            # DEC-008 Historical Action Policy Assignment (Independent of outcomes or P*)
            action_choices, action_probs = zip(*HISTORICAL_ACTION_POLICIES[scenario])
            historical_action = str(np.random.choice(action_choices, p=action_probs))

            # Latent Ground-Truth Probability Calculations
            # Calculate latent baseline recoverability P*(R | X, BASE)
            logit_base = (
                -1.0
                + (historical_success_rate * 2.5)
                - (prior_failed_attempts * 0.35)
                + (min(customer_tenure_days, 1000) / 2000.0)
                - (math.log(max(amount_rupees, 100.0)) * 0.15)
            )

            gt_p_recovery_base = round(max(0.01, min(0.99, _sigmoid(logit_base))), 4)

            # Action-conditional ground-truth probabilities P*(R | X, Action)
            # Actions add plausible domain-specific lift to baseline
            gt_p_recovery_payment_link = round(
                max(0.01, min(0.99, _sigmoid(logit_base + 0.85))), 4
            )
            gt_p_recovery_message = round(
                max(0.01, min(0.99, _sigmoid(logit_base + 0.55))), 4
            )
            gt_p_recovery_retry = round(
                max(0.01, min(0.99, _sigmoid(logit_base + 0.40))), 4
            )
            gt_p_recovery_subscription_recovery = round(
                max(0.01, min(0.99, _sigmoid(logit_base + 0.95))), 4
            )

            # Map historical_action to the corresponding latent probability
            if historical_action == ACTION_PAYMENT_LINK:
                p_selected = gt_p_recovery_payment_link
            elif historical_action == ACTION_RECOVERY_MESSAGE:
                p_selected = gt_p_recovery_message
            elif historical_action == ACTION_RETRY:
                p_selected = gt_p_recovery_retry
            elif historical_action == ACTION_SUBSCRIPTION_RECOVERY:
                p_selected = gt_p_recovery_subscription_recovery
            else:  # ACTION_STOP
                p_selected = gt_p_recovery_base * 0.2  # Very low recovery if stopped

            # Generate observed binary outcome Y ~ Bernoulli(P*)
            recovered_binary = 1 if random.random() < p_selected else 0

            records.append(
                {
                    "transaction_id": tx_id,
                    "merchant_id": merchant_id,
                    "customer_id": customer_id,
                    "scenario": scenario,
                    "amount_in_paise": amount_in_paise,
                    "amount": amount_rupees,
                    "currency": "INR",
                    "payment_method": payment_method,
                    "decline_code": decline_code,
                    "customer_tenure_days": customer_tenure_days,
                    "historical_success_rate": historical_success_rate,
                    "prior_failed_attempts": prior_failed_attempts,
                    "checkout_device": checkout_device,
                    "created_at": created_at.isoformat(),
                    "historical_action": historical_action,
                    "gt_p_recovery_base": gt_p_recovery_base,
                    "gt_p_recovery_payment_link": gt_p_recovery_payment_link,
                    "gt_p_recovery_message": gt_p_recovery_message,
                    "gt_p_recovery_retry": gt_p_recovery_retry,
                    "gt_p_recovery_subscription_recovery": gt_p_recovery_subscription_recovery,
                    "recovered": recovered_binary,
                    "dataset_version": "v1.0",
                    "random_seed": self.random_seed,
                }
            )

        df = pd.DataFrame(records)

        # Deterministic Sort by created_at and transaction_id
        df = df.sort_values(by=["created_at", "transaction_id"]).reset_index(drop=True)
        return df
