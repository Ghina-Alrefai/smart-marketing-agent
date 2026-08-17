"""Integration facade for Stable Brand DNA, page models, and Adaptive Memory.

The rest of the application talks to this module instead of importing model or
memory internals directly. This keeps the team workflow stable and makes the
intelligence layer replaceable/versionable.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from pathlib import Path
from typing import Any

from adaptive_memory import MemoryService
from adaptive_memory.models import InsightStatus, PolicyStatus

from config import settings
from database.models import Brand, ContentPlan, GeneratedPost, PostPerformanceSnapshot
from database.session import SessionLocal


_MEMORY: MemoryService | None = None
_MEMORY_LOCK = threading.Lock()


def project_root() -> Path:
    root = Path(settings.BRAND_DNA_ROOT)
    return root if root.is_absolute() else Path(__file__).resolve().parents[1] / root


def memory_service() -> MemoryService:
    """Return one process-level facade; SQLite opens short-lived connections."""
    global _MEMORY
    if _MEMORY is None:
        with _MEMORY_LOCK:
            if _MEMORY is None:
                db_path = Path(settings.ADAPTIVE_MEMORY_DB)
                if not db_path.is_absolute():
                    db_path = project_root() / db_path
                _MEMORY = MemoryService(db_path=db_path)
    return _MEMORY


def close_memory_service() -> None:
    global _MEMORY
    if _MEMORY is not None:
        _MEMORY.close()
        _MEMORY = None


def _normalized_name(value: str) -> str:
    value = value.casefold().strip()
    value = re.sub(r"[^a-z0-9\u0600-\u06ff]+", "-", value)
    return value.strip("-")


def brand_key(brand: Brand | dict[str, Any]) -> str:
    """Stable key used by the model and memory stores."""
    name = str(
        brand.get("brand_name", "") if isinstance(brand, dict) else brand.brand_name
    )
    identifier = brand.get("id") if isinstance(brand, dict) else brand.id
    normalized = _normalized_name(name)
    if "boraq" in normalized or "البراق" in normalized:
        return "al-boraq"
    return f"brand-{identifier}"


def _configured_model_keys() -> set[str]:
    return {
        value.strip()
        for value in settings.BRAND_DNA_MODEL_BRAND_KEYS.split(",")
        if value.strip()
    }


def _model_artifacts_ready() -> bool:
    root = project_root()
    return all(
        (root / "artifacts" / name).exists()
        for name in ("performance_predesign.joblib", "performance_multimodal.joblib")
    )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _split_arabic_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[,،]", value) if item.strip()]


def _language_profile(code: str | None) -> tuple[list[str], list[str]]:
    if (code or "ar").lower().startswith("ar"):
        return ["Arabic"], ["Syrian Arabic", "Modern Standard Arabic"]
    return [code or "Unknown"], [code or "Unknown"]


def build_manual_profile(brand: Brand) -> dict[str, Any]:
    """Build an honest cold-start identity from explicitly entered brand data."""
    languages, dialects = _language_profile(brand.language)
    profile: dict[str, Any] = {
        "schema_version": "2.1",
        "profile_type": "stable_brand_identity",
        "source": "manual_cold_start",
        "page_id": brand_key(brand),
        "page_name": brand.brand_name,
        "language": languages,
        "dialects": dialects,
        "business_description": brand.business_description or "",
        "target_audience": brand.target_audience or "",
        "caption_profile": {
            "common_tones": _split_arabic_list(brand.tone_of_voice),
            "common_writing_style_families": _split_arabic_list(brand.content_style),
            "preferred_cta": brand.preferred_cta or "",
            "must_use_words": list(brand.must_use_words or []),
        },
        "visual_profile": {
            "brand_colors": list(brand.brand_colors or []),
            "common_visual_styles": _split_arabic_list(brand.visual_style),
            "template_url": brand.template_url or "",
        },
        "hard_constraints": {
            "forbidden_terms": list(brand.forbidden_words or []),
        },
        "cold_start": {
            "active": True,
            "reason": "No page-specific trained model is registered for this brand.",
            "minimum_training_posts": settings.COLD_START_MIN_TRAINING_POSTS,
        },
        "separation_rule": (
            "Stable identity is authoritative. Performance-derived policies live in "
            "Adaptive Memory and cannot overwrite this profile automatically."
        ),
    }
    canonical = json.dumps(profile, ensure_ascii=False, sort_keys=True).encode("utf-8")
    profile["brand_profile_version"] = (
        "sha256:" + hashlib.sha256(canonical).hexdigest()[:16]
    )
    return profile


def _merge_explicit_constraints(profile: dict[str, Any], brand: Brand) -> dict[str, Any]:
    """Manual, human-entered constraints have authority over learned statistics."""
    merged = json.loads(json.dumps(profile, ensure_ascii=False))
    merged["page_id"] = brand_key(brand)
    merged["page_name"] = brand.brand_name
    merged["business_description"] = brand.business_description or ""
    merged["target_audience"] = brand.target_audience or ""
    merged.setdefault("hard_constraints", {})["forbidden_terms"] = list(
        brand.forbidden_words or []
    )
    merged.setdefault("caption_profile", {})["must_use_words"] = list(
        brand.must_use_words or []
    )
    if brand.preferred_cta:
        merged["caption_profile"]["preferred_cta"] = brand.preferred_cta
    merged.setdefault("visual_profile", {})["brand_colors"] = list(
        brand.brand_colors or []
    )
    merged["visual_profile"]["template_url"] = brand.template_url or ""
    # The active profile differs from the training-only profile after manual
    # constraints are overlaid, so it receives its own reproducible version.
    merged.pop("brand_profile_version", None)
    canonical = json.dumps(merged, ensure_ascii=False, sort_keys=True).encode("utf-8")
    merged["brand_profile_version"] = (
        "sha256:" + hashlib.sha256(canonical).hexdigest()[:16]
    )
    return merged


def initialize_brand_intelligence(brand_id: int, *, force: bool = False) -> dict[str, Any]:
    """Create/persist the active stable profile and select model or cold-start mode."""
    with SessionLocal() as db:
        brand = db.query(Brand).filter(Brand.id == brand_id).first()
        if not brand:
            raise ValueError(f"Brand {brand_id} not found")
        if brand.dna_profile and brand.dna_status != "uninitialized" and not force:
            return intelligence_status(brand_id, db=db)

        key = brand_key(brand)
        model_ready = key in _configured_model_keys() and _model_artifacts_ready()
        if model_ready:
            trained = _load_json(project_root() / "artifacts" / "brand_profile.json")
            profile = _merge_explicit_constraints(trained, brand)
            profile["source"] = "trained_page_history_plus_manual_constraints"
            profile["cold_start"] = {"active": False}
            status = "model_ready"
            scope = "page_specific"
            training_count = int(
                _load_json(project_root() / "artifacts" / "model_card.json").get(
                    "training_rows", 0
                )
            )
        else:
            profile = build_manual_profile(brand)
            status = "cold_start"
            scope = "none"
            training_count = 0

        brand.dna_status = status
        brand.dna_profile = profile
        brand.dna_profile_version = profile.get("brand_profile_version")
        brand.dna_model_scope = scope
        brand.dna_training_post_count = training_count
        db.commit()
        return intelligence_status(brand_id, db=db)


def get_brand_context(brand_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        brand = db.query(Brand).filter(Brand.id == brand_id).first()
        if not brand:
            return {"error": f"Brand {brand_id} not found"}
        if not brand.dna_profile or brand.dna_status == "uninitialized":
            # Close this session before the initializing function opens its own.
            pass
        else:
            return {
                "brand_key": brand_key(brand),
                "status": brand.dna_status,
                "model_scope": brand.dna_model_scope or "none",
                "profile": dict(brand.dna_profile or {}),
                "profile_version": brand.dna_profile_version,
                "prediction_available": brand.dna_status == "model_ready",
                "root": str(project_root()),
            }
    initialize_brand_intelligence(brand_id)
    return get_brand_context(brand_id)


def intelligence_status(brand_id: int, *, db=None) -> dict[str, Any]:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        brand = session.query(Brand).filter(Brand.id == brand_id).first()
        if not brand:
            raise ValueError(f"Brand {brand_id} not found")
        key = brand_key(brand)
        model_card = (
            _load_json(project_root() / "artifacts" / "model_card.json")
            if brand.dna_status == "model_ready"
            else {}
        )
        service = memory_service()
        active = service.get_active_policies(key)
        drafts = service.storage.list_policies(
            brand_id=key, status=PolicyStatus.DRAFT
        )
        all_policies = service.storage.list_policies(brand_id=key)
        all_insights = service.storage.list_insights(brand_id=key)
        evidence_count = len(service.storage.list_evidence(brand_id=key))
        validated = service.storage.list_insights(
            brand_id=key, status=InsightStatus.VALIDATED
        )
        return {
            "brand_id": brand.id,
            "brand_key": key,
            "brand_name": brand.brand_name,
            "dna_status": brand.dna_status or "uninitialized",
            "dna_profile_version": brand.dna_profile_version,
            "dna_model_scope": brand.dna_model_scope or "none",
            "dna_training_post_count": brand.dna_training_post_count or 0,
            "prediction_available": brand.dna_status == "model_ready",
            "cold_start": brand.dna_status != "model_ready",
            "model_card": model_card,
            "memory": {
                "active_policy_count": len(active),
                "draft_policy_count": len(drafts),
                "validated_insight_count": len(validated),
                "evidence_count": evidence_count,
                "insight_count": len(all_insights),
                "policy_count": len(all_policies),
                "storage_stats": service.stats(),
            },
            "authority_order": [
                "safety_and_platform",
                "stable_brand_dna",
                "human_campaign_brief",
                "active_validated_memory_policies",
                "creative_choices",
            ],
        }
    finally:
        if owns_session:
            session.close()


def bootstrap_packaged_history(brand_id: int) -> dict[str, Any]:
    """Idempotently ingest the included honest OOF evidence for AlBoraq only."""
    status = get_brand_context(brand_id)
    if status.get("status") != "model_ready":
        raise ValueError("Historical bootstrap is available only for a registered trained brand")
    evidence_path = project_root() / "outputs" / "adaptive_memory" / "all_oof_attributions.jsonl"
    result = memory_service().ingest_jsonl(
        evidence_path,
        fallback_brand_id=status["brand_key"],
        fallback_page_id=status["brand_key"],
    )
    return {"brand_key": status["brand_key"], **result}


def record_post_performance(
    generated_post_id: int,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Persist metrics and, when a real model prediction exists, ingest AM Evidence."""
    window = str(metrics.get("observation_window") or "24h")
    with SessionLocal() as db:
        post = db.query(GeneratedPost).filter(GeneratedPost.id == generated_post_id).first()
        if not post:
            raise ValueError(f"Generated post {generated_post_id} not found")
        existing = (
            db.query(PostPerformanceSnapshot)
            .filter(
                PostPerformanceSnapshot.generated_post_id == generated_post_id,
                PostPerformanceSnapshot.observation_window == window,
            )
            .first()
        )
        if existing:
            return {
                "snapshot_id": existing.id,
                "duplicate": True,
                "memory_ingested": bool(existing.memory_parent_event_id),
                "memory_parent_event_id": existing.memory_parent_event_id,
            }

        plan = db.query(ContentPlan).filter(ContentPlan.id == post.content_plan_id).first()
        brand = db.query(Brand).filter(Brand.id == plan.brand_id).first() if plan else None
        if not plan or not brand:
            raise ValueError("Post is not linked to a valid plan and brand")

        reactions = metrics.get("reactions")
        comments = metrics.get("comments")
        shares = metrics.get("shares")
        weighted = metrics.get("weighted_engagement")
        if weighted is None and all(value is not None for value in (reactions, comments, shares)):
            weighted = float(reactions) + 2.0 * float(comments) + 3.0 * float(shares)

        snapshot = PostPerformanceSnapshot(
            generated_post_id=generated_post_id,
            observation_window=window,
            actual_success=bool(metrics["actual_success"]),
            reactions=reactions,
            comments=comments,
            shares=shares,
            reach=metrics.get("reach"),
            clicks=metrics.get("clicks"),
            weighted_engagement=weighted,
            relative_performance_index=metrics.get("relative_performance_index"),
        )

        selected_id = (post.selected_candidate or {}).get("id")
        prediction = next(
            (
                item for item in (post.candidate_results or [])
                if (item.get("candidate") or {}).get("id") == selected_id
            ),
            None,
        )
        memory_result = None
        if prediction and prediction.get("prediction_available", True) \
                and prediction.get("predicted_success_probability") is not None \
                and prediction.get("feature_attributions"):
            from brand_dna.adaptive_memory import build_runtime_evidence

            prediction = dict(prediction)
            prediction["post_id"] = post.post_id or str(post.id)
            prediction["brand_profile_version"] = (
                post.dna_profile_version or prediction.get("brand_profile_version")
            )
            payload = build_runtime_evidence(
                prediction,
                {
                    **metrics,
                    "weighted_engagement": weighted,
                },
                brand_id=brand_key(brand),
                page_id=brand_key(brand),
                campaign_id=str(plan.id),
                observation_window=window,
            )
            if payload:
                memory_result = memory_service().ingest_brand_dna_payload(
                    payload, fallback_brand_id=brand_key(brand)
                )
                snapshot.memory_parent_event_id = memory_result.parent_event_id

        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return {
            "snapshot_id": snapshot.id,
            "duplicate": False,
            "memory_ingested": memory_result is not None,
            "memory_parent_event_id": snapshot.memory_parent_event_id,
            "cold_start_note": (
                None
                if memory_result is not None
                else "Metrics were stored for future training; no SHAP Evidence was invented."
            ),
        }
