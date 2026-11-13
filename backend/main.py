"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from backend import db

INSTRUCTIONS = Path(__file__).parent / "instructions.md"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    db.seed_if_empty()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


def get_db() -> Iterator[sqlite3.Connection]:
    connection = db.connect()
    try:
        yield connection
    finally:
        connection.close()


Db = Annotated[sqlite3.Connection, Depends(get_db)]


def fetch(connection: sqlite3.Connection, table: str, key: str) -> dict[str, Any]:
    row = connection.execute(
        f"SELECT body FROM {table} WHERE id = ?",  # noqa: S608
        (key,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"{key} not found")
    return json.loads(row["body"])


def document(connection: sqlite3.Connection, name: str) -> str:
    return connection.execute(
        "SELECT body FROM documents WHERE name = ?", (name,)
    ).fetchone()["body"]


def claim_row(connection: sqlite3.Connection, claim_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM claims WHERE id = ?", (claim_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"{claim_id} not found")
    return row


def claim_view(row: sqlite3.Row) -> dict[str, Any]:
    return {
        **json.loads(row["body"]),
        "status": row["status"],
        **{
            key: row[key] and json.loads(row[key])
            for key in ("decision", "signoff", "payment")
        },
    }


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(connection: Db) -> list[dict[str, Any]]:
    """List the claims queue with each claim's state."""
    rows = connection.execute(
        "SELECT claims.*, customers.body AS customer FROM claims "
        "JOIN customers ON customers.id = json_extract(claims.body, '$.customer_id') "
        "ORDER BY claims.id"
    ).fetchall()
    return [
        {
            "claim_id": claim["claim_id"],
            "customer_name": json.loads(row["customer"])["name"],
            "claim_type": claim["claim_type"],
            "summary": claim["summary"],
            "submitted_on": claim["submitted_on"],
            "amount_claimed": claim["amount_claimed"],
            "status": claim["status"],
            "decision": claim["decision"],
        }
        for row in rows
        for claim in [claim_view(row)]
    ]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, connection: Db) -> dict[str, Any]:
    """Get one claim in full, with its decision, sign-off and payment."""
    return claim_view(claim_row(connection, claim_id))


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, connection: Db) -> dict[str, Any]:
    """Get a policy with its plan's limits and its add-ons."""
    policy = fetch(connection, "policies", policy_id)
    plans = json.loads(document(connection, "plans"))
    return {
        **policy,
        "plan": next(p for p in plans["plans"] if p["plan"] == policy["plan"]),
        "add_ons": [a for a in plans["add_ons"] if a["add_on"] in policy["add_ons"]],
        "deductible_applies_to": plans["deductible_applies_to"],
    }


@app.get("/api/customers/{customer_id}/history", operation_id="get_claim_history")
def get_claim_history(customer_id: str, connection: Db) -> dict[str, Any]:
    """Get a customer's earlier claims."""
    customer = fetch(connection, "customers", customer_id)
    return {
        "customer_id": customer_id,
        "customer_since": customer["customer_since"],
        "previous_claims": customer["previous_claims"],
    }


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording(connection: Db) -> dict[str, str]:
    """Get the policy wording."""
    return {"text": document(connection, "policy_wording")}


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> dict[str, str]:
    """Get the agent's instructions."""
    return {"text": INSTRUCTIONS.read_text(encoding="utf-8")}


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(connection: Db) -> list[dict[str, Any]]:
    """List the claims handlers."""
    rows = connection.execute("SELECT body FROM handlers ORDER BY id").fetchall()
    return [
        {
            key: handler[key]
            for key in ("handler_id", "name", "role", "can_approve_over_limit")
        }
        for row in rows
        for handler in [json.loads(row["body"])]
    ]
