# SmartSocial AI v1.3.0 - Policy Review and File-by-File Project Flow

This guide answers two practical questions:

1. Which file produces, reviews, reduces, pauses, or expires a policy?
2. Which code calls which code from the user's request until learning and the next campaign?

## Exact policy ownership

| Responsibility | File | Function/class |
|---|---|---|
| Convert repeated validated Insights into a draft policy | `adaptive_memory/engine/policy_generator.py` | `PolicyGenerator.generate()` |
| Prevent weak or one-off evidence from becoming a validated Insight | `adaptive_memory/engine/validator.py` | `InsightValidator.validate()` |
| Coordinate Evidence, Insights, policy drafts, activation, and reviews | `adaptive_memory/services/memory_service.py` | `MemoryService` |
| Review an active policy and decide renew/modify/suspend/expire | `adaptive_memory/engine/policy_reviewer.py` | `PolicyReviewer.review_policy()` |
| Reduce a policy's influence to zero | `adaptive_memory/engine/policy_reviewer.py` | `_suspend()`, `_expire()`, `expire_past_validity()` |
| Persist policy status, versions, schedules, and review audit records | `adaptive_memory/storage/sqlite.py` | `save_policy()`, `update_policy()`, `save_policy_review()` |
| Trigger due reviews once per day | `services/policy_review_scheduler.py` | `_scheduler_loop()` |
| Exclude paused/expired/out-of-validity policies before generation | `adaptive_memory/services/memory_service.py` | `get_active_policies()` and `get_agent_policy_context()` |
| Manually trigger or inspect reviews through the API | `api/routers/intelligence.py` | review endpoints |
| Display review dates, evidence, and decisions | `frontend/src/pages/IntelligencePage.jsx` | `IntelligencePage` |

If “reduce the policy” means **produce the policy**, the answer is
`adaptive_memory/engine/policy_generator.py`. If it means **reduce/remove its
effect**, the answer is `adaptive_memory/engine/policy_reviewer.py`; the final
safety gate is `MemoryService.get_active_policies()`, which refuses to return an
expired policy to any agent.

## Policy lifecycle

An Adaptive Memory policy is a soft, performance-derived recommendation. It
cannot overwrite Stable Brand DNA and it cannot activate itself.

1. `PolicyGenerator.generate()` creates a `draft`.
2. A human calls `MemoryService.activate_policy()`.
3. `SQLiteStorage.activate_policy()` records:
   - `valid_from` = activation time;
   - `next_review_at` = activation + 30 days;
   - `valid_until` = next review + 15-day grace period;
   - `minimum_review_posts` = 8 by default.
4. The reviewer counts only posts whose Evidence contains the active policy ID.
5. It makes one audited decision:

| Decision | Result in code |
|---|---|
| `renew` | Keep `active`, schedule the next 30-day review, reset evidence deferrals. |
| `modify` | Pause the old version and create a new `draft` version requiring human approval. |
| `suspend` | Change status to `paused`; the agents receive none of its rules. |
| `expire` | Change status to `expired`; the agents receive none of its rules. |
| `insufficient_evidence` | Keep it temporarily, defer 14 days, and record the deferral. After the configured maximum, pause it. |

No history is overwritten. `policy_reviews` stores every decision and a modified
policy uses `family_id`, `supersedes_policy_id`, and `replacement_policy_id` to
link its versions.

## How the reviewer knows that a post used a policy

This trace is explicit:

1. `brand_dna/generation.py::get_generation_memory_context()` retrieves only
   active, valid, context-matching policy rules.
2. `services/campaign_intelligence.py::_policy_ids()` extracts the applied IDs.
3. `tools/db_tools.py::save_campaign_post()` saves them in
   `GeneratedPost.memory_policy_ids`.
4. After metrics arrive,
   `services/brand_intelligence_service.py::record_post_performance()` passes
   those IDs to `brand_dna/adaptive_memory.py::build_runtime_evidence()`.
5. The Evidence context stores them as `applied_policy_ids`.
6. `PolicyReviewer._event_applied_policy()` accepts only Evidence explicitly
   linked to the reviewed policy.

This prevents the system from claiming that an active policy caused every later
post's result.

## Full project flow

### A. Application startup

1. `main.py`
2. `database/session.py::init_db()` initializes the operational database.
3. `main.py::startup_policy_review()` starts
   `services/policy_review_scheduler.py`.
4. The scheduler immediately checks overdue policies, then checks again at the
   configured interval (daily by default).

### B. Campaign request and orchestration

The user can start through the campaign UI/API or through chat.

**Campaign UI/API route**

1. `frontend/src/api/client.js::createPlan()`
2. `api/routers/plans.py::create_plan()`
3. `frontend/src/api/client.js::triggerGeneration()`
4. `api/routers/plans.py::trigger_generation()`
5. `workflows/campaign_pipeline.py::run_campaign_pipeline()`

**Chat route**

1. `api/routers/chat.py::chat_message()`
2. `agents/orchestrator/orchestrator_agent.py::handle_message()`
3. The orchestrator classifies intent, gathers missing slots, and invokes the
   same campaign or per-post intelligence path.

### C. Campaign pipeline

`workflows/campaign_pipeline.py::run_campaign_pipeline()` is the only full
campaign orchestrator:

1. `agents/brand/brand_agent.py::analyze_brand()`
   - calls `services/brand_intelligence_service.py::get_brand_context()`;
   - returns Stable Brand DNA and the model/cold-start status.
2. `agents/strategy/strategy_agent.py::build_campaign_strategy()` builds the
   campaign-level strategy.
3. `agents/product/product_analysis_agent.py::prepare_products_context()` builds
   structured product context.
4. `agents/idea/idea_agent.py::generate_post_ideas()` creates one canonical idea
   and stable `post_id` per planned post.
5. For each idea, `_build_one_post()` calls
   `services/campaign_intelligence.py::generate_evaluated_post()`.

### D. Per-post intelligence

`services/campaign_intelligence.py::generate_evaluated_post()` performs:

1. `get_brand_context()` loads Stable Brand DNA.
2. `build_candidate_brief()` locks campaign/context fields.
3. `brand_dna/generation.py::generate_candidates()`:
   - calls `MemoryService.get_agent_policy_context()`;
   - injects only active, valid, context-matching rules;
   - generates exactly three distinct candidates;
   - validates structure, Brand DNA, content, and campaign fields;
   - runs bounded repair when needed;
   - calls `brand_dna/predictor.py` for ranking when a page-specific model exists;
   - otherwise uses honest cold-start checks without fabricated probability or SHAP.
4. `generate_design_prompt()` applies Designer policy context while Stable Brand
   DNA and an uploaded template remain authoritative.
5. `tools/image_generation.py` creates one image.
6. `tools/template_overlay.py` applies an uploaded template exactly once.
7. `tools/db_tools.py::save_campaign_post()` stores candidates, scores, model
   versions, policy IDs, trace ID, content, and design.

### E. Human approval and scheduling

1. `frontend/src/pages/CampaignDetailPage.jsx` shows the generated post.
2. `frontend/src/api/client.js::approvePost()` calls
   `api/routers/plans.py::approve_post()`.
3. Approval creates a schedule through
   `tools/db_tools.py::create_scheduled_post()`.
4. Rejection removes an existing schedule. No model or memory policy can set
   `approved=true`.

### F. Performance feedback and Adaptive Memory

1. Metrics call `POST /api/v1/intelligence/posts/{generated_post_id}/performance`.
2. `api/routers/intelligence.py::submit_performance()` calls
   `services/brand_intelligence_service.py::record_post_performance()`.
3. The operational snapshot is stored in `PostPerformanceSnapshot`.
4. `brand_dna/adaptive_memory.py::build_runtime_evidence()` converts the selected
   candidate's SHAP attribution plus real outcome into the public Evidence contract.
5. `adaptive_memory/adapters/brand_dna.py` converts the envelope into immutable,
   per-feature Evidence events.
6. `adaptive_memory/storage/sqlite.py::insert_evidence()` persists them idempotently.
7. `MemoryService.consolidate_insights()` calls:
   - `adaptive_memory/engine/learner.py::consolidate()`;
   - `adaptive_memory/engine/validator.py::validate()`.
8. `MemoryService.generate_draft_policies()` calls
   `adaptive_memory/engine/policy_generator.py::generate()`.
9. The user reviews the rules in `IntelligencePage.jsx` and activates a draft.
10. The next generation cycle can receive that active policy.

### G. Monthly policy review

1. `services/policy_review_scheduler.py` calls
   `MemoryService.review_due_policies()` once per daily check.
2. The service refreshes Insights for each due brand.
3. `PolicyReviewer.review_policy()` evaluates linked posts since activation or the
   previous review.
4. `SQLiteStorage.save_policy_review()` writes the immutable audit record.
5. Renewal updates dates; modification creates a vNext draft; suspension or
   expiry immediately stops agent injection.
6. The same engine can be triggered manually from `IntelligencePage.jsx` or the
   API without bypassing evidence thresholds.

## Databases

| Database | Purpose |
|---|---|
| `marketing_os.db` | Users, brands, products, plans, generated posts, schedules, metrics, and usage logs. |
| `outputs/adaptive_memory/app.db` | Immutable Evidence, Insights, Policies, and PolicyReview audit records. |

## Review API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/intelligence/brands/{id}/review-policies` | Review only policies currently due. |
| `POST` | `/api/v1/intelligence/policies/{policy_id}/review` | Manually review one active policy. |
| `GET` | `/api/v1/intelligence/brands/{id}/policy-reviews` | Read review history. |

## Configuration

All thresholds are in `config.py` and `.env.example`. The important defaults are:

- Review every 30 days.
- Require 8 explicitly linked evaluated posts.
- Allow a 15-day scheduler grace period.
- Defer 14 days when evidence is insufficient.
- Pause after two insufficient-evidence deferrals.
- Renew at a linked-post success rate of at least 0.60, subject to the baseline
  delta guard.

These are configurable MVP engineering thresholds, not universal marketing laws.

## Verification

```bash
pytest -q
python scripts/verify_release.py
cd frontend
npm ci
npm run build
```

The policy tests are in `tests/test_policy_review.py` and verify schedule creation,
explicit Evidence linkage, renewal, insufficient-evidence deferral, suspension,
and expiry.
