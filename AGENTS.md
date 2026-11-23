# SAS API Contributor Guidance

## Project and workflow

- This repository is the Flask API for Saved & Single. Preserve the existing API contract used by `sas-ui` unless a task explicitly changes it.
- Before implementation, read `../CONTEXT`, `../0_QUESTIONS`, and `../1_AGENT_TODOS`. The product owner wants to be involved in UX and product decisions. If scope or behavior is unclear, add a bulleted question under `UNANSWERED` at the top of `../0_QUESTIONS`, followed by a blank tab-indented line, and wait for direction instead of guessing.
- Preserve the user's wording in `AGENT_TODOS` and `0_QUESTIONS`. Follow the parent tracker workflow when completing an item.
- Keep changes focused and prefer a net reduction in code where practical.

## Stack and code style

- The API currently uses Flask, Flask-SQLAlchemy, PostgreSQL, Flask-JWT-Extended, Stripe, and a separate APScheduler process. Do not assume it is FastAPI or migrate frameworks unless explicitly requested.
- Use parameterized lowercase raw SQL for database reads. Keep model declarations compact, with table-model fields on one line where practical. Do not add enum types; use strings for new status and category values.
- Keep imports on one line where practical. Avoid unrelated refactors and preserve existing authentication, authorization, and response behavior.
- Do not edit `app/services/matching/matcher.py` unless the user explicitly authorizes changes to that file.

## Database and operations

- For every schema change, add a runnable SQL migration under `sas-api/sql/` and document the deployment order. The current API is Flask; do not imply that SQL runs automatically at startup. The parent instruction about lifespan migrations applies to FastAPI apps.
- Keep migrations safe to run in the documented order and consistent with the deployed PostgreSQL schema. Do not silently remove or rename existing data.
- Keep the web API and scheduler as separate processes. Only the dedicated scheduler runner should start scheduled jobs; avoid starting duplicate schedulers from API workers.
- Never log passwords, JWTs, Stripe secrets, personal data, or payment details. Preserve the existing Stripe Checkout, Connect, webhook, and payment-confirmation invariants.
- For walk-in authorization, an organizer's authorization only permits an otherwise-blocked signup attempt; create the attendee/payment records only after Stripe confirms successful payment.

## Delivery

- Follow existing repository setup and deployment documentation. When an API change requires a frontend, migration, environment variable, or manual production action, document the dependency in the SAS trackers as directed by the parent workflow.
- Commit and push changes to this repository when the user requests the project workflow to be completed.
