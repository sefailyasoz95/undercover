from pathlib import Path

from fastapi.routing import APIRoute

from backend import db
from backend.main import app


def test_seed_counts(client):
    connection = db.connect()
    counts = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        for table in ("claims", "policies", "customers", "handlers")
    }
    connection.close()
    assert counts == {"claims": 25, "policies": 50, "customers": 49, "handlers": 3}


def test_seed_reads_no_answer_key(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))
    read = []
    original = Path.read_text

    def spy(self, *args, **kwargs):
        read.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", spy)
    db.seed()
    assert read
    assert all(path.parent == db.DATA for path in read)


def test_seed_if_empty_keeps_the_database(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))
    db.seed_if_empty()
    connection = db.connect()
    with connection:
        connection.execute("UPDATE claims SET status = 'decided'")
    connection.close()
    db.seed_if_empty()
    connection = db.connect()
    statuses = {row[0] for row in connection.execute("SELECT status FROM claims")}
    connection.close()
    assert statuses == {"decided"}


def test_every_route_is_documented():
    for route in app.routes:
        if isinstance(route, APIRoute):
            assert route.operation_id
            assert route.description


def test_list_claims(client):
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    assert {claim["status"] for claim in claims} == {"waiting"}
    assert claims[0]["claim_id"] == "CLM-1001"
    assert claims[0]["customer_name"] == "Maya Patel"


def test_get_claim(client):
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["story"].startswith("My flight home from Rome")
    assert len(claim["items"]) == 3
    assert claim["documents"]
    assert claim["status"] == "waiting"
    assert claim["decision"] is None
    assert claim["payment"] is None


def test_unknown_ids(client):
    assert client.get("/api/claims/CLM-9999").status_code == 404
    assert client.get("/api/policies/POL-9999").status_code == 404
    assert client.get("/api/customers/CUS-9999/history").status_code == 404


def test_get_policy(client):
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"]["name"] == "UnderCover Premium"
    assert policy["plan"]["deductible"] == 50.0
    assert policy["add_ons"] == []
    assert policy["deductible_applies_to"] == ["baggage", "emergency_medical"]


def test_get_policy_with_add_ons(client):
    policies = db.load("policies.json")
    policy = next(p for p in policies if p["add_ons"])
    response = client.get(f"/api/policies/{policy['policy_id']}").json()
    assert [a["add_on"] for a in response["add_ons"]] == policy["add_ons"]


def test_get_claim_history(client):
    history = client.get("/api/customers/CUS-3001/history").json()
    assert [c["claim_id"] for c in history["previous_claims"]] == ["CLM-0412"]
    assert "email" not in history
    assert "phone" not in history


def test_get_policy_wording(client):
    text = client.get("/api/policy-wording").json()["text"]
    assert text == (db.DATA / "policy_wording.md").read_text(encoding="utf-8")


def test_get_instructions(client):
    assert "UnderCover Agent" in client.get("/api/instructions").json()["text"]


def test_list_handlers(client):
    handlers = client.get("/api/handlers").json()
    assert [h["name"] for h in handlers] == [
        "Dana Whitfield",
        "Marcus Oyelaran",
        "Priya Raman",
    ]
    assert "email" not in handlers[0]
