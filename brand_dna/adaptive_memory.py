from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from smart_social_contracts import CONTEXT_FEATURES, enrich_attributions, group_attributions_by_agent


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _context_from_attributions(attributions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        str(item["feature"]): item.get("value")
        for item in attributions
        if str(item.get("feature")) in CONTEXT_FEATURES
    }


def _event_id(
    brand_id: str,
    post_id: str,
    observation_window: str,
    model_version: str,
) -> str:
    # Stable for the same post, observation window, and model version. Re-running
    # the integration does not create a duplicate merely because processing time changed.
    raw = ":".join([brand_id, post_id, observation_window, model_version])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    return f"brand-dna-event:{digest}"


def build_runtime_evidence(
    prediction: dict[str, Any],
    actual_metrics: dict[str, Any],
    *,
    brand_id: str,
    page_id: str | None = None,
    campaign_id: str | None = None,
    observation_window: str = "24h",
    observed_at: datetime | None = None,
    success_only: bool = False,
) -> dict[str, Any] | None:
    """Build the versioned public contract sent from Brand-DNA to Adaptive Memory.

    SHAP shares remain model-attribution fields. They are deliberately not renamed to
    confidence; Adaptive Memory calculates reliability only after repeated evidence.
    """

    if "actual_success" not in actual_metrics:
        raise ValueError("actual_metrics must include the boolean field `actual_success`.")
    if not brand_id.strip():
        raise ValueError("brand_id must be a non-empty stable identifier.")

    actual_success = bool(actual_metrics["actual_success"])
    if success_only and not actual_success:
        return None

    observed_at = observed_at or _utc_now()
    attributions = enrich_attributions(prediction.get("feature_attributions", []))
    grouped = group_attributions_by_agent(attributions)
    post_id = str(prediction.get("post_id") or "unknown-post")
    model_version = str(prediction.get("model_version") or "unknown-model")

    return {
        "schema_version": "brand-dna-am-evidence-v1",
        "event_id": _event_id(
            brand_id.strip(), post_id, observation_window, model_version
        ),
        "evidence_type": "post_success_feature_attribution"
        if actual_success
        else "post_failure_feature_attribution",
        "source": {
            "outcome_source": "facebook",
            "attribution_source": "brand_dna",
        },
        "created_at": _utc_now().isoformat(),
        "observed_at": observed_at.isoformat(),
        "observation_window": observation_window,
        "brand_id": brand_id.strip(),
        "page_id": page_id,
        "post_id": post_id,
        "campaign_id": campaign_id,
        "context": _context_from_attributions(attributions),
        "brand_profile_version": prediction.get("brand_profile_version"),
        "model_version": model_version,
        "explainer_version": "shap-linear-independent-runtime-v2",
        "model_quality": prediction.get("model_quality", {}),
        "actual_success": actual_success,
        "actual_performance": {
            "relative_performance_index": actual_metrics.get(
                "relative_performance_index"
            ),
            "weighted_engagement": actual_metrics.get("weighted_engagement"),
            "reactions": actual_metrics.get("reactions"),
            "comments": actual_metrics.get("comments"),
            "shares": actual_metrics.get("shares"),
            "reach": actual_metrics.get("reach"),
            "clicks": actual_metrics.get("clicks"),
        },
        "predicted_success_probability": prediction.get(
            "predicted_success_probability"
        ),
        "baseline_probability": prediction.get("baseline_probability"),
        "shap_units": prediction.get("shap_units", "log_odds"),
        "human_approval_required": True,
        "top_success_driver": prediction.get("top_success_driver"),
        "top_success_driver_score_0_1": prediction.get(
            "top_success_driver_score_0_1"
        ),
        "feature_attributions": attributions,
        **grouped,
    }
