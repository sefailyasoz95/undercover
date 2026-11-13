"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

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


class Decision(BaseModel):
    decision: Literal["approve", "decline", "refer"]
    payout: float = Field(ge=0)
    reasons: str
    policy_section: str


class Payment(BaseModel):
    amount: float


class SignOff(BaseModel):
    handler_id: str


class Step(BaseModel):
    kind: str
    content: str


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


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


def payout_limit(connection: sqlite3.Connection) -> float:
    return json.loads(document(connection, "company"))["payout_approval_limit"]


def update_claim(
    connection: sqlite3.Connection, claim_id: str, **columns: object
) -> dict[str, Any]:
    values = {
        key: value if isinstance(value, str) else json.dumps(value)
        for key, value in columns.items()
    }
    assignments = ", ".join(f"{key} = ?" for key in values)
    with connection:
        connection.execute(
            f"UPDATE claims SET {assignments} WHERE id = ?",  # noqa: S608
            [*values.values(), claim_id],
        )
    return claim_view(claim_row(connection, claim_id))


def require_status(row: sqlite3.Row, status: str) -> None:
    if row["status"] != status:
        raise HTTPException(409, f"{row['id']} is {row['status']}, not {status}")


def payment_refusal(row: sqlite3.Row, amount: float, limit: float) -> str | None:
    decision = row["decision"] and json.loads(row["decision"])
    if not decision or decision["decision"] != "approve":
        return "Only an approved claim can be paid."
    if row["payment"]:
        return "This claim has already been paid."
    if round(amount, 2) != round(decision["payout"], 2):
        return f"The approved payout is ${decision['payout']:,.2f}."
    if decision["payout"] > limit and not row["signoff"]:
        return f"A payout over ${limit:,.2f} needs a handler's sign-off."
    return None


@app.post("/api/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(claim_id: str, connection: Db) -> dict[str, Any]:
    """Mark a waiting claim as in progress."""
    require_status(claim_row(connection, claim_id), "waiting")
    return update_claim(connection, claim_id, status="in_progress")


@app.post("/api/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(
    claim_id: str, decision: Decision, connection: Db
) -> dict[str, Any]:
    """Record the agent's decision on a claim in progress."""
    require_status(claim_row(connection, claim_id), "in_progress")
    if decision.decision != "approve" and decision.payout:
        raise HTTPException(422, "Only an approval has a payout.")
    over_limit = decision.payout > payout_limit(connection)
    return update_claim(
        connection,
        claim_id,
        status="awaiting_signoff" if over_limit else "decided",
        decision={**decision.model_dump(), "decided_at": now()},
    )


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Payment, connection: Db) -> dict[str, Any]:
    """Pay an approved claim the given amount."""
    refusal = payment_refusal(
        claim_row(connection, claim_id), payment.amount, payout_limit(connection)
    )
    if refusal:
        raise HTTPException(409, refusal)
    return update_claim(
        connection,
        claim_id,
        payment={"amount": round(payment.amount, 2), "paid_at": now()},
    )


@app.post("/api/claims/{claim_id}/signoff", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, signoff: SignOff, connection: Db) -> dict[str, Any]:
    """Sign off a claim awaiting sign-off and pay its payout."""
    row = claim_row(connection, claim_id)
    require_status(row, "awaiting_signoff")
    handler = fetch(connection, "handlers", signoff.handler_id)
    if not handler["can_approve_over_limit"]:
        raise HTTPException(403, f"{handler['name']} cannot sign off this payout.")
    update_claim(
        connection,
        claim_id,
        signoff={
            "handler_id": handler["handler_id"],
            "name": handler["name"],
            "signed_off_at": now(),
        },
    )
    payout = json.loads(row["decision"])["payout"]
    pay_claim(claim_id, Payment(amount=payout), connection)
    return update_claim(connection, claim_id, status="decided")


@app.get("/api/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str, connection: Db) -> list[dict[str, Any]]:
    """List the agent's steps on a claim, oldest first."""
    claim_row(connection, claim_id)
    rows = connection.execute(
        "SELECT id, kind, content, created_at FROM steps WHERE claim_id = ? "
        "ORDER BY id",
        (claim_id,),
    ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/claims/{claim_id}/steps", operation_id="add_step")
def add_step(claim_id: str, step: Step, connection: Db) -> dict[str, Any]:
    """Record one step of the agent's work on a claim."""
    claim_row(connection, claim_id)
    created_at = now()
    with connection:
        cursor = connection.execute(
            "INSERT INTO steps (claim_id, kind, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (claim_id, step.kind, step.content, created_at),
        )
    return {"id": cursor.lastrowid, **step.model_dump(), "created_at": created_at}
