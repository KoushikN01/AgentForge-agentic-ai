import { useState } from "react";

export default function Timeline({ events, messages }) {
  const [open, setOpen] = useState(false);

  const hasContent = events.length > 0 || messages.length > 0;

  if (!hasContent) return null;

  return (
    <div className="panel">
      {/* Collapsible header */}
      <button
        className="collapsible-header"
        onClick={() => setOpen((o) => !o)}
        style={{ width: "100%", background: "none", border: "none", color: "inherit" }}
        aria-expanded={open}
      >
        <span className="panel-label" style={{ marginBottom: 0 }}>
          Activity log
          {events.length > 0 && (
            <span className="text-muted text-small text-mono" style={{ marginLeft: 8, fontWeight: 400 }}>
              {events.length} step{events.length !== 1 ? "s" : ""}
            </span>
          )}
        </span>
        <span className={`collapsible-toggle ${open ? "open" : ""}`}>▼</span>
      </button>

      {open && (
        <div className="collapsible-body">
          {/* ── Workflow timing table ── */}
          {events.length > 0 && (
            <>
              <div
                className="timeline-row text-muted text-small"
                style={{ paddingBottom: 4, opacity: 0.6 }}
              >
                <span>Step</span>
                <span>Status</span>
                <span style={{ textAlign: "right" }}>Duration</span>
                <span>Detail</span>
              </div>
              <ul className="timeline-table">
                {events.map((event, i) => (
                  <li key={i} className="timeline-row">
                    <span className="timeline-node">{event.node}</span>
                    <span className={`pill ${event.status === "failed" ? "failed" : "passed"}`} style={{ fontSize: 10 }}>
                      {event.status === "failed" ? "failed" : "done"}
                    </span>
                    <span className="timeline-dur">{Math.round(event.duration_ms)} ms</span>
                    <span className="timeline-detail">—</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {/* ── Agent messages ── */}
          {messages.length > 0 && (
            <>
              {events.length > 0 && <hr className="divider" style={{ margin: "14px 0" }} />}
              <div className="panel-label" style={{ marginBottom: 10 }}>Agent log</div>
              <ul className="activity-list">
                {messages.map((m, i) => (
                  <li key={i} className="activity-item">
                    <span className="activity-icon text-muted">›</span>
                    <span>{m}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
