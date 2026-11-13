import pytest

from backend import db


def decide(client, claim_id, decision, payout):
    client.post(f"/api/claims/{claim_id}/start")
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "reasons": "The delay is covered and the receipts support the costs.",
            "policy_section": "Section 3, Trip Delay",
        },
    )


def pay(client, claim_id, amount):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def test_start_claim(client):
    assert client.post("/api/claims/CLM-1001/start").json()["status"] == "in_progress"
    assert client.post("/api/claims/CLM-1001/start").status_code == 409


@pytest.mark.parametrize(
    ("decision", "payout", "status"),
    [
        ("decline", 0, "decided"),
        ("refer", 0, "decided"),
        ("approve", 1000.00, "decided"),
        ("approve", 1000.01, "awaiting_signoff"),
    ],
)
def test_decision_status(client, decision, payout, status):
    claim = decide(client, "CLM-1001", decision, payout).json()
    assert claim["status"] == status
    assert claim["decision"]["decision"] == decision
    assert claim["decision"]["policy_section"] == "Section 3, Trip Delay"


def test_decision_needs_a_claim_in_progress(client):
    response = client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "decline",
            "payout": 0,
            "reasons": "Not covered.",
            "policy_section": "Section 9",
        },
    )
    assert response.status_code == 409


def test_decision_must_be_known(client):
    assert decide(client, "CLM-1001", "maybe", 0).status_code == 422


def test_only_an_approval_has_a_payout(client):
    assert decide(client, "CLM-1001", "decline", 50).status_code == 422


def test_pay_under_the_limit(client):
    decide(client, "CLM-1001", "approve", 420)
    claim = pay(client, "CLM-1001", 420).json()
    assert claim["payment"]["amount"] == 420
    assert claim["status"] == "decided"


def test_pay_over_the_limit_is_blocked(client):
    decide(client, "CLM-1001", "approve", 1500)
    response = pay(client, "CLM-1001", 1500)
    assert response.status_code == 409
    assert "sign-off" in response.json()["detail"]
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["payment"] is None
    assert claim["status"] == "awaiting_signoff"


@pytest.mark.parametrize(("decision", "payout"), [("decline", 0), ("refer", 0)])
def test_pay_without_approval(client, decision, payout):
    decide(client, "CLM-1001", decision, payout)
    assert pay(client, "CLM-1001", 100).status_code == 409


def test_pay_a_waiting_claim(client):
    assert pay(client, "CLM-1001", 100).status_code == 409


def test_pay_the_wrong_amount(client):
    decide(client, "CLM-1001", "approve", 420)
    assert pay(client, "CLM-1001", 500).status_code == 409


def test_pay_twice(client):
    decide(client, "CLM-1001", "approve", 420)
    pay(client, "CLM-1001", 420)
    assert pay(client, "CLM-1001", 420).status_code == 409


def test_sign_off_pays(client):
    decide(client, "CLM-1001", "approve", 1500)
    claim = client.post(
        "/api/claims/CLM-1001/signoff", json={"handler_id": "HND-02"}
    ).json()
    assert claim["status"] == "decided"
    assert claim["signoff"]["name"] == "Marcus Oyelaran"
    assert claim["payment"]["amount"] == 1500
    assert pay(client, "CLM-1001", 1500).status_code == 409


def test_sign_off_needs_a_claim_awaiting_sign_off(client):
    decide(client, "CLM-1001", "approve", 420)
    response = client.post(
        "/api/claims/CLM-1001/signoff", json={"handler_id": "HND-01"}
    )
    assert response.status_code == 409


def test_sign_off_needs_a_known_handler(client):
    decide(client, "CLM-1001", "approve", 1500)
    response = client.post(
        "/api/claims/CLM-1001/signoff", json={"handler_id": "HND-99"}
    )
    assert response.status_code == 404


def test_sign_off_needs_a_handler_who_can_approve(client):
    connection = db.connect()
    with connection:
        connection.execute(
            "UPDATE handlers SET body = json_set(body, '$.can_approve_over_limit', "
            "json('false')) WHERE id = 'HND-03'"
        )
    connection.close()
    decide(client, "CLM-1001", "approve", 1500)
    response = client.post(
        "/api/claims/CLM-1001/signoff", json={"handler_id": "HND-03"}
    )
    assert response.status_code == 403


def test_steps(client):
    for content in ["get_claim", "get_policy", "Approved"]:
        client.post(
            "/api/claims/CLM-1001/steps", json={"kind": "tool", "content": content}
        )
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [step["content"] for step in steps] == [
        "get_claim",
        "get_policy",
        "Approved",
    ]
    assert client.get("/api/claims/CLM-9999/steps").status_code == 404
