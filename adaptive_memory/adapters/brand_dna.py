from __future__ import annotations

import hashlib
import json
from typing import Any

from smart_social_contracts import CONTEXT_FEATURES, get_feature_spec

from adaptive_memory.models import BrandDNAEvidenceEnvelopeV1, EvidenceEvent
from adaptive_memory.models.contract import AttributionSource


def _stable_hash(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _json_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _derive_context(envelope: BrandDNAEvidenceEnvelopeV1) -> dict[str, Any]:
    context = dict(envelope.context)
    for attribution in envelope.feature_attributions:
        if attribution.feature in CONTEXT_FEATURES:
            context.setdefault(attribution.feature, attribution.value)
    return context


def _parent_event_id(
    envelope: BrandDNAEvidenceEnvelopeV1,
    brand_id: str,
) -> str:
    if envelope.event_id:
        return envelope.event_id
    fold = str(getattr(envelope, "fold", ""))
    digest = _stable_hash(
        brand_id,
        envelope.post_id,
        envelope.observation_window,
        envelope.model_version,
        envelope.explainer_version or "unknown-explainer",
        fold,
    )[:24]
    return f"brand-dna-event:{digest}"


def adapt_brand_dna_payload(
    payload: dict[str, Any] | BrandDNAEvidenceEnvelopeV1,
    *,
    fallback_brand_id: str | None = None,
    fallback_page_id: str | None = None,
    success_only: bool = False,
) -> tuple[BrandDNAEvidenceEnvelopeV1, list[EvidenceEvent]]:
    """Convert one Brand-DNA envelope into immutable per-feature Evidence events."""

    envelope = (
        payload
        if isinstance(payload, BrandDNAEvidenceEnvelopeV1)
        else BrandDNAEvidenceEnvelopeV1.model_validate(payload)
    )

    brand_id = (envelope.brand_id or fallback_brand_id or "").strip()
    if not brand_id:
        raise ValueError(
            "brand_id is required. Put it in the payload or pass fallback_brand_id."
        )
    if success_only and not envelope.actual_success:
        return envelope, []

    context = _derive_context(envelope)
    parent_event_id = _parent_event_id(envelope, brand_id)
    page_id = envelope.page_id or fallback_page_id

    if isinstance(envelope.source, AttributionSource):
        outcome_source = envelope.source.outcome_source
        attribution_source = envelope.source.attribution_source
    else:
        outcome_source = "facebook"
        attribution_source = "brand_dna"

    model_auc = envelope.model_quality.get("roc_auc")
    if model_auc is not None:
        model_auc = float(model_auc)

    events: list[EvidenceEvent] = []
    for attribution in envelope.feature_attributions:
        spec = get_feature_spec(attribution.feature)
        value_key = _json_key(attribution.value)
        idempotency_key = _stable_hash(
            parent_event_id,
            attribution.feature,
            envelope.model_version,
            envelope.explainer_version or "unknown-explainer",
        )
        events.append(
            EvidenceEvent(
                idempotency_key=idempotency_key,
                parent_event_id=parent_event_id,
                source_schema_version=envelope.schema_version,
                brand_id=brand_id,
                page_id=page_id,
                campaign_id=envelope.campaign_id,
                post_id=envelope.post_id,
                observation_window=envelope.observation_window,
                observed_at=envelope.observed_at,
                outcome_source=outcome_source,
                attribution_source=attribution_source,
                actual_success=envelope.actual_success,
                actual_performance=envelope.actual_performance.model_dump(),
                predicted_success_probability=envelope.predicted_success_probability,
                baseline_probability=envelope.baseline_probability,
                model_version=envelope.model_version,
                explainer_version=envelope.explainer_version,
                brand_profile_version=envelope.brand_profile_version,
                model_quality_roc_auc=model_auc,
                feature_name=attribution.feature,
                feature_value=attribution.value,
                feature_value_key=value_key,
                owner_agent=spec.owner_agent,
                feature_role=spec.role,
                direction=attribution.direction,
                raw_shap_log_odds=attribution.raw_shap_log_odds,
                success_support_0_1=attribution.success_support_0_1,
                success_opposition_0_1=attribution.success_opposition_0_1,
                importance_0_1=attribution.importance_0_1,
                context=context,
                human_approval_required=envelope.human_approval_required,
            )
        )

    return envelope, events
