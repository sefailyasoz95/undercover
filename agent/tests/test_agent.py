from itertools import count

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend import main as backend

ids = count()


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def call(name, **args):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": str(next(ids))}]
    )


def stub(*replies):
    return StubModel(messages=iter(replies))


def decision(payout):
    return call(
        "record_decision",
        decision="approve",
        payout=payout,
        reasons="The crew problem delayed the flight past the waiting period.",
        policy_section="Section 3, Trip Delay",
    )


READS = [
    call("get_claim"),
    call("get_policy"),
    call("get_claim_history"),
    call("get_policy_wording"),
]


def test_run_approves_and_pays(client):
    reply = main.run(
        "CLM-1001",
        "thread-1",
        stub(
            *READS,
            decision(420),
            call("pay_claim", amount=420),
            AIMessage(content="Approved and paid $420.00."),
        ),
    )
    assert reply == "Approved and paid $420.00."
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["payout"] == 420
    assert claim["payment"]["amount"] == 420
    results = [
        step["content"]
        for step in client.get("/api/claims/CLM-1001/steps").json()
        if step["kind"] == "result"
    ]
    assert results[1].startswith('get_policy: {"policy_id": "POL-2001"')
    assert results[2].startswith('get_claim_history: {"customer_id": "CUS-3001"')


def test_run_cannot_pay_over_the_limit(client):
    reply = main.run(
        "CLM-1001",
        "thread-1",
        stub(
            decision(1500),
            call("pay_claim", amount=1500),
            AIMessage(content="Approved; the payment waits for sign-off."),
        ),
    )
    assert reply == "Approved; the payment waits for sign-off."
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "awaiting_signoff"
    assert claim["payment"] is None
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert "sign-off" in steps[-2]["content"]


def test_run_without_a_decision_refers(client):
    main.run("CLM-1001", "thread-1", stub(AIMessage(content="I am not sure.")))
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["decision"] == "refer"
    assert claim["decision"]["reasons"] == main.NO_DECISION


def test_run_that_fails_refers(client):
    with pytest.raises(RuntimeError):
        main.run("CLM-1001", "thread-1", stub())
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["decision"]["decision"] == "refer"


def test_run_needs_a_waiting_claim(client):
    client.post("/api/claims/CLM-1001/start")
    with pytest.raises(Exception, match="409 Conflict"):
        main.run("CLM-1001", "thread-1", stub())


def test_steps_are_recorded_in_order(client):
    main.run(
        "CLM-1001",
        "thread-1",
        stub(call("get_claim"), decision(420), AIMessage(content="Done.")),
    )
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [step["kind"] for step in steps] == [
        "tool",
        "result",
        "tool",
        "result",
        "reply",
    ]
    assert steps[0]["content"] == "get_claim({})"
    assert steps[-1]["content"] == "Done."


def test_long_results_are_shortened(client):
    main.run(
        "CLM-1001",
        "thread-1",
        stub(call("get_policy_wording"), AIMessage(content="Done.")),
    )
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert steps[1]["content"].endswith("...")
    assert len(steps[1]["content"]) < main.STEP_LENGTH + 50


def test_instructions_come_from_the_backend(client, monkeypatch):
    seen = []
    create_agent = main.create_agent

    def spy(model, tools, system_prompt):
        seen.append(system_prompt)
        return create_agent(model, tools=tools, system_prompt=system_prompt)

    monkeypatch.setattr(main, "create_agent", spy)
    main.run("CLM-1001", "thread-1", stub(AIMessage(content="Done.")))
    assert seen == [client.get("/api/instructions").json()["text"]]


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"


def test_run_agent_route(client, monkeypatch):
    monkeypatch.setattr(main, "model", lambda: stub(decision(420)))
    response = client.post("/api/claims/CLM-1001/run")
    assert response.json() == {"claim_id": "CLM-1001", "status": "started"}
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["decision"]["payout"] == 420
    assert client.post("/api/claims/CLM-1001/run").status_code == 409


def test_run_queue_route(client, monkeypatch):
    ran = []
    monkeypatch.setattr(backend.agent, "run", lambda claim_id, _: ran.append(claim_id))
    client.post("/api/claims/CLM-1001/start")
    response = client.post("/api/queue/run").json()
    assert len(response["claim_ids"]) == 24
    assert ran == response["claim_ids"]


def test_run_queue_keeps_going_after_a_failure(client, monkeypatch):
    ran = []

    def run(claim_id, _):
        ran.append(claim_id)
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(backend.agent, "run", run)
    client.post("/api/queue/run")
    assert len(ran) == 25
