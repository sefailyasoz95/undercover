import { useCallback, useEffect, useState } from "react";
import { api, type Claim, type Handler, type Policy, type Step } from "./api";
import { decisionLabels, label, money } from "./format";
import { StatusBadge } from "./StatusBadge";
import { usePolling } from "./usePolling";

const stepLabels: Record<Step["kind"], string> = {
  tool: "Called",
  result: "Result",
  reply: "Reply",
};

function ClaimDetails({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <div className="stack">
      <div className="panel">
        <h2>The customer's story</h2>
        <p className="story">{claim.story}</p>
      </div>
      <div className="panel">
        <h2>Items claimed</h2>
        <table>
          <tbody>
            {claim.items.map((item) => (
              <tr key={item.description}>
                <td>{item.description}</td>
                <td>{label(item.category)}</td>
                <td className="number mono">{money(item.amount)}</td>
              </tr>
            ))}
            <tr>
              <th colSpan={2}>Total claimed</th>
              <td className="number mono">{money(claim.amount_claimed)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="panel">
        <h2>Documents</h2>
        <div className="documents">
          {claim.documents.map((document) => (
            <article key={document.name}>
              <h3>{document.name}</h3>
              <p>{document.content}</p>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

function PolicyPanel({ policy }: Readonly<{ policy: Policy }>) {
  return (
    <div className="panel">
      <h2>Policy</h2>
      <dl>
        <dt>Policy</dt>
        <dd className="mono">{policy.policy_id}</dd>
        <dt>Plan</dt>
        <dd>{policy.plan.name}</dd>
        <dt>Add-ons</dt>
        <dd>
          {policy.add_ons.map((addOn) => addOn.name).join(", ") || "None"}
        </dd>
        <dt>Trip</dt>
        <dd>
          {policy.trip.destination}, {policy.trip.departs_on} to{" "}
          {policy.trip.returns_on}
        </dd>
        <dt>Trip cost</dt>
        <dd className="mono">{money(policy.trip.trip_cost)}</dd>
        <dt>Travelers</dt>
        <dd>{policy.travelers.join(", ")}</dd>
        <dt>Bought</dt>
        <dd className="mono">{policy.purchased_on}</dd>
      </dl>
    </div>
  );
}

function SignOffForm({
  claim,
  onSignedOff,
}: Readonly<{ claim: Claim; onSignedOff: (claim: Claim) => void }>) {
  const [handlers, setHandlers] = useState<Handler[]>([]);
  const [handlerId, setHandlerId] = useState("");

  useEffect(() => {
    void api.handlers().then((found) => {
      setHandlers(found);
      setHandlerId(found[0]?.handler_id ?? "");
    });
  }, []);

  async function signOff() {
    onSignedOff(await api.signOff(claim.claim_id, handlerId));
  }

  return (
    <div className="held">
      <p>
        The payout of {money(claim.decision?.payout ?? 0)} is over the approval
        limit and is held until a handler signs off.
      </p>
      <div className="sign-off">
        <label>
          Handler{" "}
          <select
            value={handlerId}
            onChange={(event) => {
              setHandlerId(event.target.value);
            }}
          >
            {handlers.map((handler) => (
              <option key={handler.handler_id} value={handler.handler_id}>
                {handler.name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={!handlerId}
          onClick={() => void signOff()}
        >
          Sign off and pay
        </button>
      </div>
    </div>
  );
}

function Payment({ claim }: Readonly<{ claim: Claim }>) {
  if (claim.payment) {
    return (
      <p>
        Paid <span className="mono">{money(claim.payment.amount)}</span> on{" "}
        {claim.payment.paid_at.slice(0, 10)}
        {claim.signoff && `, signed off by ${claim.signoff.name}`}.
      </p>
    );
  }
  if (claim.decision?.decision === "approve") return <p>Not paid yet.</p>;
  return null;
}

function DecisionPanel({
  claim,
  onRun,
  onSignedOff,
}: Readonly<{
  claim: Claim;
  onRun: () => void;
  onSignedOff: (claim: Claim) => void;
}>) {
  const { decision } = claim;
  return (
    <div className="panel">
      <h2>Decision</h2>
      {claim.status === "waiting" && (
        <>
          <p>The agent has not worked on this claim yet.</p>
          <button type="button" onClick={onRun}>
            Run agent
          </button>
        </>
      )}
      {claim.status === "in_progress" && (
        <p>The agent is working on this claim.</p>
      )}
      {decision && (
        <>
          <p className="payout">
            {decisionLabels[decision.decision]} {money(decision.payout)}
          </p>
          <p>{decision.reasons}</p>
          <p className="muted">{decision.policy_section}</p>
        </>
      )}
      {claim.status === "awaiting_signoff" && (
        <SignOffForm claim={claim} onSignedOff={onSignedOff} />
      )}
      <Payment claim={claim} />
    </div>
  );
}

function StepsPanel({ steps }: Readonly<{ steps: Step[] }>) {
  return (
    <div className="panel">
      <h2>The agent's steps</h2>
      {steps.length === 0 ? (
        <p className="muted">No steps yet.</p>
      ) : (
        <ol className="steps" aria-label="The agent's steps">
          {steps.map((step) => (
            <li key={step.id}>
              <span className="step-kind">{stepLabels[step.kind]}</span>
              {step.kind === "reply" ? (
                <p>{step.content}</p>
              ) : (
                <pre>{step.content}</pre>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export function ClaimView({ claimId }: Readonly<{ claimId: string }>) {
  const [claim, setClaim] = useState<Claim>();
  const [policy, setPolicy] = useState<Policy>();
  const [steps, setSteps] = useState<Step[]>([]);
  const [started, setStarted] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    Promise.all([api.claim(claimId), api.steps(claimId)])
      .then(([found, foundSteps]) => {
        setClaim(found);
        setSteps(foundSteps);
      })
      .catch((reason: unknown) => {
        setError(`${claimId} could not be loaded: ${String(reason)}`);
      });
  }, [claimId]);

  const working =
    claim?.status === "in_progress" || (started && claim?.status === "waiting");
  usePolling(load, 2000, working);

  const policyId = claim?.policy_id;
  useEffect(() => {
    if (policyId) void api.policy(policyId).then(setPolicy);
  }, [policyId]);

  async function runAgent() {
    setStarted(true);
    await api.runAgent(claimId);
    load();
  }

  if (error) return <p className="error">{error}</p>;
  if (!claim) return <p>Loading {claimId}...</p>;

  return (
    <section>
      <div className="title-row">
        <h1>
          <span className="mono">{claim.claim_id}</span>{" "}
          {label(claim.claim_type)}
        </h1>
        <StatusBadge status={claim.status} />
      </div>
      <p className="muted">
        {claim.summary}. Submitted {claim.submitted_on}, incident on{" "}
        {claim.incident_date} in {claim.incident_location}.
      </p>
      <div className="claim-grid">
        <ClaimDetails claim={claim} />
        <div className="stack">
          <DecisionPanel
            claim={claim}
            onRun={() => void runAgent()}
            onSignedOff={setClaim}
          />
          {policy && <PolicyPanel policy={policy} />}
          <StepsPanel steps={steps} />
        </div>
      </div>
    </section>
  );
}
