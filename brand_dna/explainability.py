from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from smart_social_contracts import enrich_attributions, group_attributions_by_agent


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def explain_linear_model(classifier, background: np.ndarray, X: np.ndarray):
    import shap

    masker = shap.maskers.Independent(background)
    explainer = shap.LinearExplainer(classifier, masker)
    explanation = explainer(X)
    return np.asarray(explanation.values, dtype=float), float(explainer.expected_value)


def aggregate_encoded_shap(
    shap_values: np.ndarray,
    feature_names: list[str],
    feature_groups: list[str],
    group_order: list[str],
    feature_values: dict[str, Any],
) -> dict[str, Any]:
    raw = {group: 0.0 for group in group_order}
    absolute_mass = {group: 0.0 for group in group_order}
    for value, _, group in zip(shap_values, feature_names, feature_groups, strict=True):
        if group not in raw:
            raw[group] = 0.0
            absolute_mass[group] = 0.0
        raw[group] += float(value)
        absolute_mass[group] += abs(float(value))

    positive_total = sum(max(value, 0.0) for value in raw.values())
    negative_total = sum(max(-value, 0.0) for value in raw.values())
    absolute_total = sum(absolute_mass.values())

    attributions = []
    for group in group_order:
        value = raw.get(group, 0.0)
        if value > 1e-12:
            direction = "supports_success"
        elif value < -1e-12:
            direction = "opposes_success"
        else:
            direction = "neutral"
        attributions.append(
            {
                "feature": group,
                "value": _json_value(feature_values.get(group)),
                "direction": direction,
                "raw_shap_log_odds": round(value, 10),
                "success_support_0_1": round(
                    max(value, 0.0) / positive_total if positive_total else 0.0, 10
                ),
                "success_opposition_0_1": round(
                    max(-value, 0.0) / negative_total if negative_total else 0.0, 10
                ),
                "importance_0_1": round(
                    absolute_mass.get(group, 0.0) / absolute_total if absolute_total else 0.0,
                    10,
                ),
            }
        )

    enriched_attributions = enrich_attributions(attributions)
    supporting = [
        item for item in enriched_attributions if item["raw_shap_log_odds"] > 0
    ]
    top_driver = max(
        supporting, key=lambda item: item["success_support_0_1"], default=None
    )
    return {
        "feature_attributions": enriched_attributions,
        "top_success_driver": top_driver["feature"] if top_driver else None,
        "top_success_driver_score_0_1": top_driver["success_support_0_1"]
        if top_driver
        else 0.0,
        **group_attributions_by_agent(enriched_attributions),
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def summarize_evidence(records: list[dict[str, Any]]) -> dict[str, Any]:
    successes = [record for record in records if record.get("actual_success") is True]
    failures = [record for record in records if record.get("actual_success") is False]
    if not successes:
        raise ValueError("No actual successful posts were available for summary.")

    success_by_feature: dict[str, list[dict[str, Any]]] = defaultdict(list)
    failure_by_feature: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in successes:
        for item in record["feature_attributions"]:
            success_by_feature[item["feature"]].append(item)
    for record in failures:
        for item in record["feature_attributions"]:
            failure_by_feature[item["feature"]].append(item)

    weights = np.asarray(
        [max(float(record.get("actual_performance", {}).get("relative_performance_index") or 0.1), 0.1) for record in successes],
        dtype=float,
    )
    weights = weights / weights.sum()

    feature_scores = []
    for feature, success_items in success_by_feature.items():
        support = np.asarray([item["success_support_0_1"] for item in success_items], dtype=float)
        raw_success = np.asarray([item["raw_shap_log_odds"] for item in success_items], dtype=float)
        failure_items = failure_by_feature.get(feature, [])
        raw_failure = np.asarray(
            [item["raw_shap_log_odds"] for item in failure_items], dtype=float
        )
        feature_scores.append(
            {
                "feature": feature,
                "successful_post_count": len(success_items),
                "mean_success_support_0_1": round(float(support.mean()), 10),
                "performance_weighted_support_0_1": round(
                    float(np.dot(weights[: len(support)], support)), 10
                ),
                "positive_sign_rate_in_successes": round(float((raw_success > 0).mean()), 10),
                "mean_raw_shap_success_log_odds": round(float(raw_success.mean()), 10),
                "mean_raw_shap_failure_log_odds": round(
                    float(raw_failure.mean()) if len(raw_failure) else 0.0, 10
                ),
                "success_minus_failure_raw_shap": round(
                    float(raw_success.mean() - raw_failure.mean())
                    if len(raw_failure)
                    else float(raw_success.mean()),
                    10,
                ),
            }
        )

    feature_scores.sort(
        key=lambda item: item["performance_weighted_support_0_1"], reverse=True
    )

    value_groups: dict[tuple[str, str], list[float]] = defaultdict(list)
    for record in successes:
        for item in record["feature_attributions"]:
            value_key = json.dumps(item.get("value"), ensure_ascii=False, sort_keys=True)
            value_groups[(item["feature"], value_key)].append(item["success_support_0_1"])
    value_scores = []
    for (feature, value_key), values in value_groups.items():
        if len(values) < 2:
            continue
        value_scores.append(
            {
                "feature": feature,
                "value": json.loads(value_key),
                "support_count": len(values),
                "mean_success_support_0_1": round(float(np.mean(values)), 10),
            }
        )
    value_scores.sort(
        key=lambda item: (item["mean_success_support_0_1"], item["support_count"]),
        reverse=True,
    )

    return {
        "schema_version": "1.0",
        "filter": "actual_success == true",
        "successful_post_count": len(successes),
        "failed_post_count_used_for_contrast": len(failures),
        "interpretation": (
            "Scores are normalized shares of the model's positive SHAP evidence among "
            "actual successful posts. They explain the model and are not causal effects."
        ),
        "feature_scores": feature_scores,
        "repeated_feature_value_scores": value_scores,
    }


def write_jsonl(records: list[dict[str, Any]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
