# Status

The claims pilot, built from `docs/PLAN.md`. All six phases are done.

- `backend/`: FastAPI on SQLite. `db.py` seeds the database from `data/`, never from `data/evals/` or `data/security/`. The read operations serve the queue, claims, policies with their plans, claim history (without contact details), the policy wording, the agent's instructions (`backend/instructions.md`) and the handlers. The write operations start a claim, record a decision, pay a claim, sign off and record the agent's steps. A payment over the limit in `data/company.json` ($1,000) is refused until a handler signs off, and signing off makes the payment. `run_agent` and `run_queue` run the agent in the background
- `agent/`: the UnderCover Agent, `run(claim_id, thread_id)`. It fetches its instructions from the backend, reads the claim, its policy and plan, the customer's claim history and the policy wording, records a decision and pays approved claims, all through the backend's API. Its tools are bound to the claim it works on. It posts each step to the backend as it goes, and a run that ends without a decision refers the claim
- `dashboard/`: React in the UnderCover brand, light and dark. The queue (`#/`) lists every claim with its state and a count for each state, and works the queue. The claim view (`#/claims/<id>`) shows the claim, its policy, the decision and payment, and the agent's steps, refreshed every two seconds while the agent works; it runs the agent on a waiting claim, and a handler signs off a held payout there. The instructions view (`#/instructions`) is read only
- `e2e/`: Playwright tests of the queue, the instructions, a decided claim and sign-off. They play the agent's work through the API, so they never call a model

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on http://localhost:5173. The backend creates and seeds `backend/undercover.db` on first start
- `uv run -m backend.seed` resets the database to the claims in `data/`. Set `UNDERCOVER_DB` to use another file
- `uv run -m agent CLM-1001` runs the agent on one claim from the command line, with the backend running. "Run agent" on a claim and "Work the queue" do the same from the dashboard
- The agent uses `openai/gpt-6-luna` with low reasoning effort, or the model in `MODEL_NAME` (such as `openrouter/free`), with `OPENROUTER_API_KEY` from `.env`
- `npm run check` runs every check. The end-to-end tests start their own backend on port 8100 and dashboard on port 5174 with a fresh database at `e2e/e2e.db`, so they never touch the database you use with `npm run dev`
