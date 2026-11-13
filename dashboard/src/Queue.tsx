import { useCallback, useState } from "react";
import { api, type ClaimSummary, type Status } from "./api";
import { decisionLabels, label, money, statusLabels } from "./format";
import { StatusBadge } from "./StatusBadge";
import { usePolling } from "./usePolling";

const statuses = Object.keys(statusLabels) as Status[];

export function Queue() {
  const [claims, setClaims] = useState<ClaimSummary[]>();
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(() => {
    api
      .claims()
      .then(setClaims)
      .catch(() => {
        setError("The backend is not responding.");
      });
  }, []);
  usePolling(load, 3000, true);

  async function workQueue() {
    const { claim_ids } = await api.runQueue();
    setMessage(
      `The agent is working through ${String(claim_ids.length)} claims.`,
    );
    load();
  }

  if (error) return <p className="error">{error}</p>;
  if (!claims) return <p>Loading the queue...</p>;

  const waiting = claims.filter((claim) => claim.status === "waiting").length;

  return (
    <section>
      <div className="title-row">
        <h1>Claims queue</h1>
        <button
          type="button"
          disabled={waiting === 0}
          onClick={() => void workQueue()}
        >
          Work the queue
        </button>
      </div>
      {message && <p role="status">{message}</p>}
      <ul className="counts" aria-label="Claims by state">
        {statuses.map((status) => (
          <li key={status} className="panel">
            <span className="count">
              {claims.filter((claim) => claim.status === status).length}
            </span>
            <StatusBadge status={status} />
          </li>
        ))}
      </ul>
      <div className="panel table-panel">
        <table>
          <thead>
            <tr>
              <th>Claim</th>
              <th>Customer</th>
              <th>Type</th>
              <th>Submitted</th>
              <th className="number">Claimed</th>
              <th>State</th>
              <th>Decision</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((claim) => (
              <tr key={claim.claim_id}>
                <td className="mono">
                  <a href={`#/claims/${claim.claim_id}`}>{claim.claim_id}</a>
                </td>
                <td>{claim.customer_name}</td>
                <td>{label(claim.claim_type)}</td>
                <td className="mono">{claim.submitted_on}</td>
                <td className="number mono">{money(claim.amount_claimed)}</td>
                <td>
                  <StatusBadge status={claim.status} />
                </td>
                <td>
                  {claim.decision &&
                    `${decisionLabels[claim.decision.decision]} ${money(claim.decision.payout)}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
