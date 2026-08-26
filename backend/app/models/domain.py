import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy import (
    String, Numeric, Float, Integer, Boolean, DateTime, Text, JSON, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def generate_uuid() -> str:
    """Generate string UUID primary keys."""
    return str(uuid.uuid4())


def current_utc_time() -> datetime:
    """Generate timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, nullable=False)

    customers: Mapped[list["Customer"]] = relationship("Customer", back_populates="merchant", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="merchant")
    policies: Mapped[list["Policy"]] = relationship("Policy", back_populates="merchant")


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("merchant_id", "email", name="uk_merchant_customer_email"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(String(36), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    historical_success_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    historical_transaction_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, nullable=False)

    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="customers")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="customer")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("idx_transactions_status", "status"),
        Index("idx_transactions_mode", "mode"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    merchant_id: Mapped[str] = mapped_column(String(36), ForeignKey("merchants.id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False)
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    razorpay_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    razorpay_payment_link_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    razorpay_subscription_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    razorpay_invoice_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(50), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recovery_cycle: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="SIMULATION", nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, onupdate=current_utc_time, nullable=False)

    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="transactions")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="transactions")
    events: Mapped[list["Event"]] = relationship("Event", back_populates="transaction")
    diagnoses: Mapped[list["Diagnosis"]] = relationship("Diagnosis", back_populates="transaction")
    decision_contexts: Mapped[list["DecisionContext"]] = relationship("DecisionContext", back_populates="transaction")
    recovery_attempts: Mapped[list["RecoveryAttempt"]] = relationship("RecoveryAttempt", back_populates="transaction")
    recovery_attributions: Mapped[list["RecoveryAttribution"]] = relationship("RecoveryAttribution", back_populates="transaction")
    audit_events: Mapped[list["AuditEvent"]] = relationship("AuditEvent", back_populates="transaction")
    human_reviews: Mapped[list["HumanReview"]] = relationship("HumanReview", back_populates="transaction")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_idempotency", "idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    transaction_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_source: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    razorpay_event_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, nullable=False)

    transaction: Mapped[Optional["Transaction"]] = relationship("Transaction", back_populates="events")


class DecisionContext(Base):
    __tablename__ = "decision_contexts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, nullable=False)

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="decision_contexts")
    action_scores: Mapped[list["RecoveryActionScore"]] = relationship("RecoveryActionScore", back_populates="decision_context", cascade="all, delete-orphan")


class RecoveryActionScore(Base):
    __tablename__ = "recovery_action_scores"
    __table_args__ = (
        UniqueConstraint("decision_context_id", "action", name="uk_decision_action"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    decision_context_id: Mapped[str] = mapped_column(String(36), ForeignKey("decision_contexts.id", ondelete="CASCADE"), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    recovery_probability: Mapped[float] = mapped_column(Float, nullable=False)
    expected_gross_recovery: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    intervention_cost: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    expected_net_recovery_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, nullable=False)

    decision_context: Mapped["DecisionContext"] = relationship("DecisionContext", back_populates="action_scores")


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=False)
    failure_code: Mapped[str] = mapped_column(String(100), nullable=False)
    failure_category: Mapped[str] = mapped_column(String(100), nullable=False)
    root_cause_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    diagnosis_source: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, nullable=False)

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="diagnoses")


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    merchant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("merchants.id"), nullable=True)
    policy_version: Mapped[str] = mapped_column(String(50), default="v1.0", nullable=False)
    max_recovery_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    max_auto_action_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=50000.00, nullable=False)
    min_recovery_probability: Mapped[float] = mapped_column(Float, default=0.15, nullable=False)
    cooldown_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, nullable=False)

    merchant: Mapped[Optional["Merchant"]] = relationship("Merchant", back_populates="policies")


class RecoveryAttempt(Base):
    __tablename__ = "recovery_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=False)
    decision_context_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("decision_contexts.id"), nullable=True)
    logical_operation_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(100), nullable=False)
    action_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    policy_status: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    execution_status: Mapped[str] = mapped_column(String(50), nullable=False)
    external_resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    external_resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    razorpay_payment_link_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    razorpay_reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, nullable=False)

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="recovery_attempts")


class RecoveryAttribution(Base):
    __tablename__ = "recovery_attributions"
    __table_args__ = (
        UniqueConstraint("transaction_id", "recovery_attempt_id", name="uk_tx_attempt_attribution"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=False)
    recovery_attempt_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("recovery_attempts.id"), nullable=True)
    recovery_source: Mapped[str] = mapped_column(String(50), nullable=False)
    attribution_status: Mapped[str] = mapped_column(String(50), nullable=False)
    attribution_method: Mapped[str] = mapped_column(String(50), nullable=False)
    attribution_window_minutes: Mapped[int] = mapped_column(Integer, default=1440, nullable=False)
    recovered_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    refunded_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    intervention_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recovery_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, nullable=False)

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="recovery_attributions")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("idx_audit_tx_hash", "transaction_id", "event_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    state_from: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    state_to: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, nullable=False)

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="audit_events")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(50), nullable=False)
    dataset_size: Mapped[int] = mapped_column(Integer, nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, default=42, nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    configuration_version: Mapped[str] = mapped_column(String(50), nullable=False)
    code_commit_sha: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mode: Mapped[str] = mapped_column(String(20), default="SIMULATION", nullable=False)
    revenue_at_risk: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    baseline_recovered_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    recoverai_gross_recovered_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    incremental_recovered_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    baseline_recovery_rate: Mapped[float] = mapped_column(Float, nullable=False)
    recoverai_recovery_rate: Mapped[float] = mapped_column(Float, nullable=False)
    summary_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, nullable=False)


class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=False)
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=current_utc_time, nullable=False)

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="human_reviews")
