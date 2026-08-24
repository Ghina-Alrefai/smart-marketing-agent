# SmartSocial AI v1.3.2 — Campaign recovery QA report

Prepared: 2026-08-24

## Automated result

| Area | Verification | Result |
|---|---|---|
| Full Python/backend suite | `pytest -q` | 58 passed |
| Malformed Gemini JSON | first response invalid, second valid | Retried and recovered |
| Exhausted JSON retries | all responses invalid | Raised; never returned `{}` |
| Idea contract | zero or wrong post count | Rejected |
| Pipeline success gate | Idea Agent returns zero posts | Plan stored as `failed` |
| Campaign deletion | plan has failed LLM usage row | Plan deleted; usage row preserved and detached |
| Frontend production bundle | `npm run build` | Passed |

The only Python warning is emitted by the installed third-party
FastAPI/Starlette TestClient compatibility layer.

## External-service boundary

The real Gemini provider was not charged during the deterministic suite. Its SDK
configuration, JSON parsing, retries, validators, monitoring boundaries, and
pipeline behavior were tested using controlled provider responses. Run one small
real campaign after placing the owner's replacement `GOOGLE_API_KEY` in `.env`.

## Acceptance scenario

1. Start the server and create a one- or three-day campaign.
2. Poll the campaign until it reaches `done`, `done_with_errors`, or `failed`.
3. Confirm `done` always has at least one post.
4. If the provider exhausts JSON retries, confirm the red failure message and
   `إعادة توليد الحملة` button appear.
5. Delete the campaign and confirm the request returns HTTP 204 even when the
   Consumption tab contains model attempts for it.
