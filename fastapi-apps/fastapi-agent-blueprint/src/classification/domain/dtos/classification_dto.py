from pydantic import BaseModel, Field


class ClassificationDTO(BaseModel):
    """Structured output from the classification agent."""

    category: str = Field(..., description="Predicted category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0–1)")
    reasoning: str = Field(..., description="Brief reasoning for the classification")
