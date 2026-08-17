from __future__ import annotations

from pydantic import BaseModel, Field


class IngestionResult(BaseModel):
    parent_event_id: str
    extracted_count: int = Field(ge=0)
    inserted_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)


class ConsolidationResult(BaseModel):
    brand_id: str
    evidence_count: int = Field(ge=0)
    candidate_insight_count: int = Field(ge=0)
    validated_insight_count: int = Field(ge=0)
    rejected_insight_count: int = Field(ge=0)
