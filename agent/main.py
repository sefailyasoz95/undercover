"""The UnderCover Agent."""

import json
import os
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
STEP_LENGTH = 1000
NO_DECISION = "The agent did not reach a decision, so the claim needs a handler."


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    url = os.getenv("BACKEND_URL") or "http://localhost:8000"
    return httpx.Client(base_url=url, timeout=30)


def get(path: str) -> Any:
    with backend() as client:
        response = client.get(path)
    response.raise_for_status()
    return response.json()


def post(path: str, body: dict[str, Any]) -> Any:
    with backend() as client:
        response = client.post(path, json=body)
    response.raise_for_status()
    return response.json()


def attempt(path: str, body: dict[str, Any]) -> Any:
    """Post for the agent: a refusal comes back as data for it to read."""
    with backend() as client:
        response = client.post(path, json=body)
    if response.is_client_error:
        return {"refused": response.json()["detail"]}
    response.raise_for_status()
    return response.json()


def tools(claim_id: str) -> list[BaseTool]:
    """Return the agent's tools, bound to the claim it is working on."""

    @tool
    def get_claim() -> dict[str, Any]:
        """Get the claim: the customer's story, the items claimed and the documents."""
        return get(f"/api/claims/{claim_id}")

    @tool
    def get_policy() -> dict[str, Any]:
        """Get the claim's policy with its plan's limits, its add-ons and the trip."""
        policy_id = get(f"/api/claims/{claim_id}")["policy_id"]
        return get(f"/api/policies/{policy_id}")

    @tool
    def get_claim_history() -> dict[str, Any]:
        """Get the customer's earlier claims."""
        customer_id = get(f"/api/claims/{claim_id}")["customer_id"]
        return get(f"/api/customers/{customer_id}/history")

    @tool
    def get_policy_wording() -> str:
        """Get the policy wording, the contract with the customer."""
        return get("/api/policy-wording")["text"]

    @tool
    def record_decision(
        decision: Literal["approve", "decline", "refer"],
        payout: float,
        reasons: str,
        policy_section: str,
    ) -> dict[str, Any]:
        """Record the decision, the payout (0 unless approved), two or three
        sentences of reasons and the section of the policy wording it rests on."""
        return attempt(
            f"/api/claims/{claim_id}/decision",
            {
                "decision": decision,
                "payout": payout,
                "reasons": reasons,
                "policy_section": policy_section,
            },
        )

    @tool
    def pay_claim(amount: float) -> dict[str, Any]:
        """Pay the approved payout on the claim."""
        return attempt(f"/api/claims/{claim_id}/payment", {"amount": amount})

    return [
        get_claim,
        get_policy,
        get_claim_history,
        get_policy_wording,
        record_decision,
        pay_claim,
    ]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def steps(message: BaseMessage) -> list[dict[str, str]]:
    """Turn one message from the run into the steps the dashboard shows."""
    if isinstance(message, ToolMessage):
        content = message.text
        if len(content) > STEP_LENGTH:
            content = content[:STEP_LENGTH] + "..."
        return [{"kind": "result", "content": f"{message.name}: {content}"}]
    if not isinstance(message, AIMessage):
        return []
    found = [{"kind": "reply", "content": message.text}] if message.text else []
    return found + [
        {"kind": "tool", "content": f"{call['name']}({json.dumps(call['args'])})"}
        for call in message.tool_calls
    ]


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its final reply."""
    instructions = get("/api/instructions")["text"]
    post(f"/api/claims/{claim_id}/start", {})
    agent = create_agent(
        llm or model(), tools=tools(claim_id), system_prompt=instructions
    )
    reply = ""
    try:
        for update in agent.stream(
            {"messages": [{"role": "user", "content": f"Decide claim {claim_id}."}]},
            config={"configurable": {"thread_id": thread_id}},
            stream_mode="updates",
        ):
            for node in update.values():
                for message in node["messages"]:
                    for step in steps(message):
                        post(f"/api/claims/{claim_id}/steps", step)
                    if isinstance(message, AIMessage) and message.text:
                        reply = message.text
    finally:
        if get(f"/api/claims/{claim_id}")["status"] == "in_progress":
            post(
                f"/api/claims/{claim_id}/decision",
                {
                    "decision": "refer",
                    "payout": 0,
                    "reasons": NO_DECISION,
                    "policy_section": "None",
                },
            )
    return reply
