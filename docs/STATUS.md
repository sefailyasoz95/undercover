# Status

The claims pilot, built from `docs/PLAN.md`. Done so far: phase 1.

- `backend/`: FastAPI on SQLite. `db.py` seeds the database from `data/` (never `data/evals/` or `data/security/`); the read operations serve the queue, claims, policies with their plans, claim history, the policy wording, the agent's instructions (`backend/instructions.md`) and the handlers
- `agent/`: still the skeleton's hello-world agent
- `dashboard/`: still the skeleton's health page
- `e2e/`: one test of that page

## Running it

- `uv run -m backend.seed` rebuilds the database at `backend/undercover.db` (or the path in `UNDERCOVER_DB`). The backend seeds it on startup when it is missing
- `npm run dev` starts the backend and the dashboard
