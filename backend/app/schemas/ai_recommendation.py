"""
RecoverAI - AI Recommendation Response Pydantic Schema (Step 13A)

Defines the structured output data model returned by the AI Recommender service.
"""

from pydantic import BaseModel, Field


class AIRecommendationResponse(BaseModel):
    """
    Structured AI Recommendation payload synthesizing diagnostic context,
    customer history, and ENRV action rankings into advisory recovery strategies.

    SAFETY BOUNDARY GUARANTEES:
    - Pure advisory response contract.
    - Zero capability to execute payment calls or mutate state directly.
    """
    recommended_action: str = Field(
        ...,
        min_length=1,
        description="Recommended recovery action identifier (e.g. PAYMENT_LINK, RECOVERY_MESSAGE)"
    )
    rationale_text: str = Field(
        ...,
        min_length=1,
        description="Diagnostic explanation and rationale supporting the recommendation"
    )
    customer_message_template: str = Field(
        ...,
        min_length=1,
        description="Personalized customer communication message template"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Recommendation confidence score bounded between 0.0 and 1.0"
    )
