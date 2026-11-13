# Status

The claims pilot, built from `docs/PLAN.md`. Done so far: phases 1 to 4.

- `backend/`: FastAPI on SQLite. `db.py` seeds the database from `data/` (never `data/evals/` or `data/security/`); the read operations serve the queue, claims, policies with their plans, claim history, the policy wording, the agent's instructions (`backend/instructions.md`) and the handlers. The write operations start a claim, record a decision, pay a claim, sign off and record the agent's steps. A payment over the $1,000 limit in `data/company.json` is refused until a handler signs off, and signing off makes the payment
- `agent/`: the UnderCover Agent, `run(claim_id, thread_id)`. It fetches its instructions from the backend, reads the claim, its policy and plan, the customer's claim history and the policy wording, records a decision and pays approved claims, all through the backend's API. Its tools are bound to the claim it works on. It posts each step to the backend as it goes, and a run that ends without a decision refers the claim. The backend runs it in the background through `run_agent` and `run_queue`
- `dashboard/`: React in the UnderCover brand, light and dark. The queue (`#/`) lists every claim with its state and a count for each state, and works the queue; the instructions view (`#/instructions`) shows the agent's instructions, read only. The claim view (`#/claims/<id>`) is a placeholder for now
- `e2e/`: one test of that page

## Running it

- `uv run -m backend.seed` rebuilds the database at `backend/undercover.db` (or the path in `UNDERCOVER_DB`). The backend seeds it on startup when it is missing
- `npm run dev` starts the backend and the dashboard
- `uv run -m agent CLM-1001` runs the agent on one claim, with the backend running. It uses the model in `MODEL_NAME`, or `openai/gpt-6-luna`, and the key `OPENROUTER_API_KEY` in `.env`
