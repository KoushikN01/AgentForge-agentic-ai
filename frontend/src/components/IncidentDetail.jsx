import { useEffect, useRef, useState } from "react";
import { api, IN_PROGRESS_STATUSES } from "../api.js";
import StatusPill from "./StatusBadge.jsx";
import Timeline from "./Timeline.jsx";

const POLL_MS = 1500;

// ── Helpers ──────────────────────────────────────────────────────────

function confidenceClass(c) {
  if (c >= 0.75) return "high";
  if (c >= 0.45) return "medium";
  return "low";
}

// Derive a readable step list from the current incident status + available data
function buildWorkflowSteps(incident, evidence, root_cause, patch_proposal, test_result, review_result) {
  const status = incident.status;
  const isDone = (s) => s === "done";

  const steps = [
    {
      key: "triage",
      label: "Evidence collected",
      note: `${evidence.length} signal${evidence.length !== 1 ? "s" : ""} gathered`,
      state: evidence.length > 0 ? "done" : status === "in_progress" ? "current" : "pending",
    },
    {
      key: "root_cause",
      label: "Root cause identified",
      note: root_cause ? `${(root_cause.confidence * 100).toFixed(0)}% confidence` : "Analysing…",
      state: root_cause ? "done" : evidence.length > 0 && status === "in_progress" ? "current" : "pending",
    },
    {
      key: "patch",
      label: "Fix proposed",
      note: patch_proposal ? patch_proposal.target_file : "Generating fix…",
      state: patch_proposal ? "done" : root_cause && status === "in_progress" ? "current" : "pending",
    },
    {
      key: "test",
      label: "Sandbox tests",
      note: test_result
        ? test_result.all_passed ? "All passed ✓" : "Some failed"
        : "Pending",
      state: test_result
        ? test_result.all_passed ? "done" : "failed"
        : patch_proposal && status === "in_progress" ? "current" : "pending",
    },
    {
      key: "review",
      label: "Safety reviewed",
      note: review_result
        ? `${review_result.risk_level} risk — ${review_result.approved ? "approved" : "rejected"}`
        : "Pending",
      state: review_result ? "done" : test_result && status === "in_progress" ? "current" : "pending",
    },
    {
      key: "approval",
      label: "Human approval",
      note: status === "awaiting_approval"
        ? "Waiting for you"
        : status === "resolved" ? "Approved — fix applied"
        : status === "failed" ? "Rejected or timed out"
        : "Pending",
      state: status === "awaiting_approval"
        ? "awaiting"
        : status === "resolved" ? "done"
        : status === "failed" && (review_result || test_result) ? "failed"
        : "pending",
    },
  ];

  return steps;
}

// ── Sub-components ────────────────────────────────────────────────────

function WorkflowRail({ steps }) {
  return (
    <div className="workflow-rail">
      {steps.map((step, i) => (
        <div key={step.key} className={`workflow-step ${step.state}`}>
          <div className="step-icon">
            {step.state === "done" ? "✓"
              : step.state === "current" ? "…"
              : step.state === "awaiting" ? "!"
              : step.state === "failed" ? "✗"
              : i + 1}
          </div>
          <div className="step-content">
            <div className="step-label">{step.label}</div>
            <div className="step-note">{step.note}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────

export default function IncidentDetail({ incidentId, onBack }) {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [deciding, setDeciding] = useState(false);
  const intervalRef = useRef(null);

  const refresh = async () => {
    try {
      const data = await api.getIncident(incidentId);
      setState(data);
      setError(null);
      if (!IN_PROGRESS_STATUSES.has(data.incident.status) && intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    setState(null);
    refresh();
    intervalRef.current = setInterval(refresh, POLL_MS);
    return () => intervalRef.current && clearInterval(intervalRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incidentId]);

  async function startInvestigation() {
    try {
      await api.startInvestigation(incidentId);
      await refresh();
      if (!intervalRef.current) intervalRef.current = setInterval(refresh, POLL_MS);
    } catch (e) {
      setError(e.message);
    }
  }

  async function decide(approved) {
    setDeciding(true);
    try {
      await api.approve(incidentId, approved);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setDeciding(false);
    }
  }

  // Loading skeleton
  if (!state) {
    return (
      <div className="panel" style={{ color: "var(--muted)", fontSize: 13.5 }}>
        Loading incident…
      </div>
    );
  }

  const {
    incident, evidence, knowledge_context, root_cause,
    patch_proposal, test_result, review_result, events, messages, retry_count,
  } = state;

  const workflowSteps = buildWorkflowSteps(
    incident, evidence, root_cause, patch_proposal, test_result, review_result
  );

  const confLevel = root_cause ? confidenceClass(root_cause.confidence) : null;

  return (
    <>
      {error && (
        <div className="error-banner">
          <span>⚠</span> {error}
        </div>
      )}

      {/* ── 1. Incident header ── */}
      <div className="panel">
        <div className="flex justify-between items-center gap-8 mb-8">
          <div>
            <div className="panel-title">{incident.title}</div>
            <div className="panel-tech-label" style={{ marginBottom: 4 }}>
              ID: {incidentId}
            </div>
          </div>
          <StatusPill status={incident.status} />
        </div>

        <p style={{ marginBottom: 14 }}>{incident.description}</p>

        <dl className="kv">
          <dt>Severity</dt>
          <dd><span className={`pill ${incident.severity || "medium"}`}>{incident.severity || "medium"}</span></dd>
          <dt>Reported</dt>
          <dd className="text-mono text-small">{new Date(incident.created_at).toLocaleString()}</dd>
          {retry_count > 0 && (
            <>
              <dt>Retries</dt>
              <dd>{retry_count} after earlier fix didn't pass</dd>
            </>
          )}
        </dl>

        {incident.status === "new" && (
          <div style={{ marginTop: 14 }}>
            <button
              className="btn btn-primary"
              id="start-investigation-btn"
              onClick={startInvestigation}
            >
              Start investigation →
            </button>
          </div>
        )}

        {incident.status === "in_progress" && (
          <div className="notice investigating-notice mt-12">
            <span>◉</span>
            Agents are investigating — this panel updates automatically every 1.5 s.
          </div>
        )}
      </div>

      {/* ── 2. Workflow progress ── */}
      <div className="panel">
        <div className="panel-label">Workflow progress</div>
        <WorkflowRail steps={workflowSteps} />
      </div>

      {/* ── 3. Evidence ── */}
      {evidence.length > 0 && (
        <div className="panel">
          <div className="panel-label">Evidence collected</div>
          <div className="panel-title">What the agents found</div>

          <ul className="snippet-list">
            {evidence.map((item, i) => <li key={i}>{item}</li>)}
          </ul>

          {knowledge_context.length > 0 && (
            <>
              <hr className="divider" style={{ margin: "14px 0" }} />
              <div className="panel-label" style={{ marginBottom: 8 }}>Relevant documentation</div>
              <ul className="snippet-list">
                {knowledge_context.map((item, i) => <li key={i}>{item}</li>)}
              </ul>
            </>
          )}
        </div>
      )}

      {/* ── 4. Root cause ── */}
      {root_cause && (
        <div className="panel">
          <div className="panel-label">Root cause analysis</div>
          <div className="panel-title">Why it's happening</div>
          <p style={{ marginBottom: 14 }}>{root_cause.root_cause}</p>

          <div className="confidence-bar-wrap">
            <span className="text-muted text-small text-mono" style={{ whiteSpace: "nowrap" }}>
              Confidence {(root_cause.confidence * 100).toFixed(0)}%
            </span>
            <div className="confidence-bar-track">
              <div
                className={`confidence-bar-fill ${confLevel}`}
                style={{ width: `${(root_cause.confidence * 100).toFixed(0)}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── 5. Patch proposal ── */}
      {patch_proposal && (
        <div className="panel">
          <div className="panel-label">Proposed fix</div>
          <div className="panel-title">What the agent wants to change</div>
          <p style={{ marginBottom: 12 }}>{patch_proposal.explanation}</p>

          <div className="chips">
            <span className="chip">{patch_proposal.target_file}</span>
          </div>

          <pre className="code">
            <span className="diff-del">- {patch_proposal.original_snippet}</span>{"\n"}
            <span className="diff-add">+ {patch_proposal.replacement_snippet}</span>
          </pre>
        </div>
      )}

      {/* ── 6. Test result ── */}
      {test_result && (
        <div className="panel">
          <div className="flex justify-between items-center mb-8">
            <div className="panel-label" style={{ marginBottom: 0 }}>Sandbox verification</div>
            <span className={`pill ${test_result.all_passed ? "passed" : "failed"}`}>
              {test_result.all_passed ? "All passed" : "Some failed"}
            </span>
          </div>
          <p>{test_result.summary}</p>
          <div className="safety-note">
            🔒 Tests ran in an isolated sandbox — your real project was not touched.
          </div>
        </div>
      )}

      {/* ── 7. Safety review ── */}
      {review_result && (
        <div className="panel">
          <div className="flex justify-between items-center mb-8">
            <div className="panel-label" style={{ marginBottom: 0 }}>Safety review</div>
            <span className={`pill ${review_result.approved ? "approved" : "rejected"}`}>
              {review_result.approved ? "Approved" : "Rejected"} · {review_result.risk_level} risk
            </span>
          </div>

          <p style={{ marginBottom: 10 }}>{review_result.reasoning}</p>

          {review_result.concerns.length > 0 && (
            <ul className="snippet-list">
              {review_result.concerns.map((c, i) => <li key={i}>{c}</li>)}
            </ul>
          )}
        </div>
      )}

      {/* ── 8. Human-in-the-loop approval gate ── */}
      {incident.status === "awaiting_approval" && (
        <div className="approval-gate">
          <div className="approval-gate-title">
            <span>⚠</span> Your decision is required
          </div>
          <p>
            The proposed fix has passed sandbox testing and the safety review above.
            It will <strong>only</strong> be applied to the real project if you approve it now.
          </p>

          <div className="approval-fields">
            <dl className="kv">
              <dt>File</dt>
              <dd className="text-mono text-small">{patch_proposal?.target_file ?? "—"}</dd>
              <dt>Tests</dt>
              <dd>{test_result?.all_passed ? "All passed" : "—"}</dd>
              <dt>Risk level</dt>
              <dd>{review_result?.risk_level ?? "—"}</dd>
            </dl>
          </div>

          <div className="approval-actions">
            <button
              className="btn btn-approve"
              id="approve-btn"
              disabled={deciding}
              onClick={() => decide(true)}
            >
              {deciding ? "Working…" : "Apply fix to project"}
            </button>
            <button
              className="btn btn-reject"
              id="reject-btn"
              disabled={deciding}
              onClick={() => decide(false)}
            >
              Reject
            </button>
          </div>

          <div className="safety-note">
            🔒 Approving will apply the exact diff shown above. You can always revert via git.
          </div>
        </div>
      )}

      {/* ── 9. Terminal states ── */}
      {incident.status === "resolved" && (
        <div className="decision-result approved">
          <div className="panel-label" style={{ color: "var(--green)", marginBottom: 6 }}>Resolved</div>
          <p>You approved the fix — it has been applied to the real project.</p>
        </div>
      )}

      {incident.status === "failed" && (
        <div className="decision-result rejected">
          <div className="panel-label" style={{ color: "var(--red)", marginBottom: 6 }}>Failed</div>
          <p>
            {review_result || test_result
              ? "No fix passed testing and review within the retry limit, or it was rejected."
              : "The investigation did not complete — see the agent log below."}
          </p>
        </div>
      )}

      {/* ── 10. Activity log ── */}
      <Timeline events={events} messages={messages} />
    </>
  );
}
