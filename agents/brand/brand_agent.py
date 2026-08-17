"""Brand Agent compatibility adapter backed by persisted Stable Brand DNA."""
from __future__ import annotations

from services.brand_intelligence_service import get_brand_context
from tools.db_tools import get_brand


def analyze_brand(brand_id: int) -> dict:
    """
    Return the stable, versioned Brand-DNA profile plus the legacy raw brand
    object expected by the team's existing Strategy/Product/Idea agents.
    """
    brand = get_brand(brand_id)
    if not brand:
        return {"error": f"Brand {brand_id} not found"}

    context = get_brand_context(brand_id)
    if "error" in context:
        return context
    return {
        **context["profile"],
        "_brand": brand,
        "_intelligence": {
            "status": context["status"],
            "model_scope": context["model_scope"],
            "profile_version": context["profile_version"],
            "prediction_available": context["prediction_available"],
        },
    }
