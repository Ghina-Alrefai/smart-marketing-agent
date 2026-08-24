# SmartSocial AI v1.3.1 — QA and stabilization report

Prepared: 2026-08-24

## Result

The deterministic application paths pass the automated and offline integration
suite. The frontend production bundle was rebuilt on Linux from a clean
`npm ci`. The release package is intentionally clean: it contains no `.env`,
credentials, runtime database, logs, caches, installed dependencies, or user
uploads.

## Verified features

| Area | Verification | Result |
|---|---|---|
| Python/backend suite | `pytest -q` | 53 passed |
| API routing | protected routes, static-before-dynamic routes, JSON 404, 405 + `Allow` | Passed |
| Authorization | user/brand/product/plan/post/schedule/policy/chat ownership and admin override | Passed |
| Campaign launch | explicit Arabic campaign intent, no redundant chat LLM call, one background claim | Passed |
| Brand DNA model runtime | concurrent encoder reuse, bundle reuse, artifact refresh after retraining | Passed |
| Candidate generation | memory injection, repair attempt, low-score stop, draft-policy exclusion | Passed |
| Adaptive Memory | evidence idempotency, consolidation gates, draft/activation separation | Passed |
| Policy lifecycle | monthly schedule, renew/modify/suspend/expire, grace and evidence thresholds | Passed |
| Uploads | HTML/corrupt/oversized rejection; safe PNG/JPEG/WebP extension derived by server | Passed |
| Committee demo | direct invocation from repository root; two runs keep one plan and one post | Passed |
| CLI configuration | app, Adaptive Memory CLI, and Brand-DNA CLI share the same memory DB default | Passed |
| Frontend source | 20 source modules parsed/import-checked; 49 API contracts; 13 page smoke renders | Passed |
| Frontend production build | Vite 5.4.21, 1,636 modules transformed | Passed |
| OpenAPI | 49 paths, 54 operations, no duplicate operation IDs | Passed |
| Release integrity | syntax/JSON, required files, manifest SHA-256, package denylist, ZIP integrity | Passed |

The only test warning is emitted by the third-party FastAPI/Starlette TestClient
compatibility layer. Project-owned `datetime.utcnow()` warnings were removed.

## Important repairs

- Cached both SentenceTransformer encoders and both joblib model bundles once
  per API process, with thread-safe first load and automatic bundle refresh when
  an artifact changes.
- Added startup warm-up plus a direct `scripts/preload_models.py` entry point.
- Removed cross-account data access and chat-session reuse across users/brands.
- Fixed `/products/user/{id}` and `/plans/user/{id}` route shadowing.
- Claimed campaign generation before enqueueing, preventing duplicate jobs.
- Used deterministic intent/entity rules for explicit campaign requests so the
  chat layer does not perform redundant Gemini calls before the pipeline.
- Bounded and content-validated all uploads; added `nosniff` responses.
- Kept unknown API paths and wrong methods out of the React SPA fallback.
- Made production startup fail closed when the default JWT key or admin password
  remains configured; Railway/Nixpacks explicitly set production mode.
- Fixed React Query invalidation, stale local users, brand selection, cross-brand
  conversations, repeated actions, error/request-ID display, and partial-create
  duplicate behavior.
- Made the committee demo direct and idempotent, unified Adaptive Memory database
  defaults, removed project datetime deprecations, and hardened release checks.

## External-service boundary

The following require the owner's real credentials and network access and were
not sent to live providers during this audit:

- real Gemini text/image generation;
- Google OAuth token verification;
- first-time Hugging Face model download;
- publication to an external social platform.

Their local adapters, failure boundaries, dry-run paths, caching behavior, and
mocked generation/retry contracts were tested. Before a real acceptance test,
configure a new `.env`, run `python scripts/preload_models.py`, and exercise one
small Gemini campaign with budget/usage monitoring enabled.

## Security handoff

The source ZIP supplied for this audit contained a non-placeholder Google API
key in `.env`. That file and value are not present in this release. Revoke/rotate
the old key before using the project, then place only the replacement in the
local `.env` created from `.env.example`.

For code-to-code project flow and the monthly policy-review owner, see
`docs/POLICY_REVIEW_AND_PROJECT_FLOW.md`.
