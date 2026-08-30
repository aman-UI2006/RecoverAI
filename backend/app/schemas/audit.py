"""
RecoverAI - Audit REST API Schemas (Step 25)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class AuditEventResponse(BaseModel):
    """Base response schema for an AuditEvent record."""
    id: str = Field(..., description="Audit event UUID.")
    transaction_id: str = Field(..., description="Transaction UUID.")
    event_type: str = Field(..., description="Lifecycle event type.")
    actor: str = Field(..., description="System actor or component.")
    state_from: Optional[str] = Field(None, description="State before transition.")
    state_to: Optional[str] = Field(None, description="Target state after transition.")
    details: Dict[str, Any] = Field(default_factory=dict, description="Event detail payload.")
    previous_hash: str = Field(..., description="SHA-256 hash of previous audit event in chain.")
    event_hash: str = Field(..., description="SHA-256 cryptographic hash of current audit event.")
    created_at: datetime = Field(..., description="Creation timestamp.")

    model_config = ConfigDict(from_attributes=True)


class AuditPaginatedResponse(BaseModel):
    """Paginated list response for audit log entries."""
    total: int = Field(..., description="Total matching audit records count.")
    page: int = Field(..., description="Current page index.")
    limit: int = Field(..., description="Page size limit.")
    items: List[AuditEventResponse] = Field(..., description="Audit record items.")


class AuditVerificationResponse(BaseModel):
    """Cryptographic hash chain verification response."""
    transaction_id: str = Field(..., description="Transaction UUID evaluated.")
    is_valid: bool = Field(..., description="True if hash chain integrity is intact.")
    total_events: int = Field(..., description="Number of events evaluated in chain.")
    tampered_event_id: Optional[str] = Field(None, description="ID of tampered record if chain verification failed.")
    error_message: Optional[str] = Field(None, description="Verification error description if invalid.")
    genesis_hash: str = Field(..., description="Cryptographic genesis hash anchor.")
