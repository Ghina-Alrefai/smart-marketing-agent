from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from adaptive_memory.models import Policy, PolicyRule
from adaptive_memory.services import MemoryService
from brand_dna.generation import generate_candidates
from smart_social_contracts import AgentType


BRIEF = {
    "topic": "إطلاق هاتف جديد مع هدية",
    "campaign_goal": "Lead Generation",
    "campaign_type": "Product Launch + Giveaway",
    "product_category": "Mobile",
    "brand_name": "Samsung",
    "day": "الخميس",
    "time_bucket": "Evening",
    "season": "الصيف",
}

PROFILE = {
    "page_name": "Al Boraq Telecom",
    "language": ["Arabic"],
    "dialects": ["Syrian Arabic with MSA/English product terms"],
    "hard_constraints": {
        "required_logo_position": "Samsung: top-left; Al Boraq: top-right",
        "required_color_families": ["blue", "white"],
    },
}


def _candidate(identifier: str, caption: str, *, hook: str) -> dict:
    return {
        "id": identifier,
        "caption": caption,
        "campaign_goal": BRIEF["campaign_goal"],
        "campaign_type": BRIEF["campaign_type"],
        "product_category": BRIEF["product_category"],
        "brand_name": BRIEF["brand_name"],
        "day": BRIEF["day"],
        "time_bucket": BRIEF["time_bucket"],
        "season": BRIEF["season"],
        "language": "Arabic",
        "dialect": "Syrian Arabic with MSA/English product terms",
        "cta_presence": "Explicit",
        "cta_type": "Enter giveaway",
        "tone": "Playful, Promotional",
        "writing_style": "Question hook; Product reveal",
        "hook_type": hook,
        "content_pillar": "New Arrivals & Giveaways",
        "number_of_ctas": 1,
        "number_of_hashtags": 0,
        "number_of_products": 1,
        "contains_human": "No",
        "dominant_colors": "blue; white; cyan",
        "logo_position": "Samsung: top-left; Al Boraq: top-right",
        "text_in_image": "Galaxy A55; متوفر الآن",
        "visual_style": "Product hero poster",
        "layout_type": "Centered product with headline",
        "image_count": 1,
        "is_product_post": "Yes",
    }


def _good_batch() -> list[dict]:
    return [
        _candidate(
            "candidate-a",
            "بدك تكتشف Galaxy الجديد وتدخل السحب على هدية مميزة؟ اطلب التفاصيل الآن.",
            hook="Question + giveaway",
        ),
        _candidate(
            "candidate-b",
            "وصل Galaxy الجديد للبراق مع مزايا قوية وفرصة هدية. منشن رفيقين وشارك معنا.",
            hook="Announcement + product reveal",
        ),
        _candidate(
            "candidate-c",
            "كاميرا أوضح وأداء أسرع بتجربة Galaxy الجديدة. راسلنا لتعرف العرض المتاح.",
            hook="Benefit + direct CTA",
        ),
    ]


class FakeClient:
    def __init__(self, payloads: list[object]):
        self.payloads = list(payloads)
        self.prompts: list[str] = []
        self.models = self

    def generate_content(self, *, model: str, contents: str):
        self.prompts.append(contents)
        payload = self.payloads.pop(0)
        return SimpleNamespace(text=json.dumps(payload, ensure_ascii=False))


def _ranker(probabilities: list[float]):
    def rank(candidates, mode, root=None):
        results = []
        for candidate, probability in zip(candidates, probabilities, strict=True):
            results.append(
                {
                    "post_id": candidate["id"],
                    "predicted_success_probability": probability,
                    "feature_attributions": [],
                    "candidate": dict(candidate),
                }
            )
        results.sort(
            key=lambda item: item["predicted_success_probability"], reverse=True
        )
        for index, item in enumerate(results, start=1):
            item["rank"] = index
        return results

    return rank


def _activate_copywriter_policy(service: MemoryService) -> str:
    rule = PolicyRule(
        description="Prefer a question-based opening hook for this campaign context.",
        feature_name="hook_style",
        feature_value="question",
        conditions={"campaign_goal": BRIEF["campaign_goal"]},
        source_insight_id="insight-question-hook",
        confidence_0_1=0.82,
        priority=2,
    )
    policy = Policy(
        brand_id="al-boraq",
        target_agent=AgentType.COPYWRITER,
        version=1,
        rules=[rule],
        source_insight_ids=["insight-question-hook"],
    )
    service.storage.save_policy(policy)
    service.activate_policy(policy.id, approved_by="test-reviewer")
    return rule.description


def test_active_memory_is_injected_into_runtime_prompt(tmp_path: Path) -> None:
    service = MemoryService(db_path=tmp_path / "memory.db")
    description = _activate_copywriter_policy(service)
    client = FakeClient([_good_batch()])

    result = generate_candidates(
        BRIEF,
        PROFILE,
        memory_service=service,
        brand_id="al-boraq",
        max_attempts=1,
        min_success_probability=0.50,
        client=client,
        ranker=_ranker([0.81, 0.73, 0.68]),
    )

    assert result["status"] == "ready"
    assert result["adaptive_memory_applied"] is True
    assert description in client.prompts[0]
    assert "Active Adaptive Memory context" in client.prompts[0]
    service.close()


def test_invalid_first_batch_is_repaired_on_second_attempt() -> None:
    client = FakeClient([_good_batch()[:2], _good_batch()])
    result = generate_candidates(
        BRIEF,
        PROFILE,
        max_attempts=2,
        min_success_probability=0.50,
        client=client,
        ranker=_ranker([0.75, 0.70, 0.65]),
    )

    assert result["status"] == "ready"
    assert result["attempt_count"] == 2
    assert result["attempt_history"][0]["stage"] == "validation"
    assert "Exactly three candidates are required" in client.prompts[1]


def test_all_low_scoring_batches_stop_with_needs_review() -> None:
    client = FakeClient([_good_batch(), _good_batch()])
    result = generate_candidates(
        BRIEF,
        PROFILE,
        max_attempts=2,
        min_success_probability=0.70,
        client=client,
        ranker=_ranker([0.44, 0.39, 0.31]),
    )

    assert result["status"] == "needs_review"
    assert result["human_approval_required"] is True
    assert len(result["candidates"]) == 3
    assert all(
        not candidate["quality_gate"]["passed"]
        for candidate in result["candidates"]
    )
    assert result["attempt_history"][-1]["accepted"] is False


def test_draft_policy_is_not_injected(tmp_path: Path) -> None:
    service = MemoryService(db_path=tmp_path / "memory.db")
    rule = PolicyRule(
        description="This draft must not reach generation.",
        feature_name="hook_style",
        feature_value="question",
        conditions={},
        source_insight_id="draft-insight",
        confidence_0_1=0.80,
        priority=2,
    )
    service.storage.save_policy(
        Policy(
            brand_id="al-boraq",
            target_agent=AgentType.COPYWRITER,
            version=1,
            rules=[rule],
            source_insight_ids=["draft-insight"],
        )
    )
    client = FakeClient([_good_batch()])

    result = generate_candidates(
        BRIEF,
        PROFILE,
        memory_service=service,
        brand_id="al-boraq",
        max_attempts=1,
        client=client,
        ranker=_ranker([0.8, 0.7, 0.6]),
    )

    assert result["adaptive_memory_applied"] is False
    assert rule.description not in client.prompts[0]
    service.close()
