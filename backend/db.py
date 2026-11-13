"""The UnderCover database: SQLite, seeded from the business data in data/."""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DATA = Path(__file__).parent.parent / "data"
DEFAULT_PATH = Path(__file__).parent / "undercover.db"

SCHEMA = """
CREATE TABLE documents (name TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE policies (id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE customers (id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE handlers (id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE claims (
    id TEXT PRIMARY KEY,
    body TEXT NOT NULL,
    status TEXT NOT NULL,
    decision TEXT,
    signoff TEXT,
    payment TEXT
);
CREATE TABLE steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def path() -> Path:
    """Return the database file, from UNDERCOVER_DB or the default."""
    return Path(os.getenv("UNDERCOVER_DB") or DEFAULT_PATH)


def connect() -> sqlite3.Connection:
    """Open a connection to the database."""
    connection = sqlite3.connect(path(), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def load(name: str) -> Any:
    """Read one JSON file from data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def seed() -> None:
    """Rebuild the database from data/."""
    path().unlink(missing_ok=True)
    wording = (DATA / "policy_wording.md").read_text(encoding="utf-8")
    with connect() as connection:
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO documents VALUES (?, ?)",
            [
                ("company", json.dumps(load("company.json"))),
                ("plans", json.dumps(load("plans.json"))),
                ("policy_wording", wording),
            ],
        )
        for table, file, key in [
            ("policies", "policies.json", "policy_id"),
            ("customers", "customers.json", "customer_id"),
            ("handlers", "handlers.json", "handler_id"),
        ]:
            connection.executemany(
                f"INSERT INTO {table} VALUES (?, ?)",  # noqa: S608
                [(row[key], json.dumps(row)) for row in load(file)],
            )
        connection.executemany(
            "INSERT INTO claims (id, body, status) VALUES (?, ?, 'waiting')",
            [(claim["claim_id"], json.dumps(claim)) for claim in load("claims.json")],
        )
    connection.close()


def seed_if_empty() -> None:
    """Seed the database unless it already exists."""
    if not path().exists():
        seed()
