import { useEffect, useState } from "react";
import { api } from "../api.js";
import StatusPill from "./StatusBadge.jsx";

const SEVERITY_LABEL = { low: "Low", medium: "Medium", high: "High", critical: "Critical" };

export default function Dashboard({ onSelect, selectedId }) {
  const [incidents, setIncidents] = useState([]);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({ title: "", description: "", severity: "medium" });
  const [submitting, setSubmitting] = useState(false);
  const [formOpen, setFormOpen] = useState(true);

  const load = () =>
    api.listIncidents().then(setIncidents).catch((e) => setError(e.message));

  useEffect(() => { load(); }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.title.trim() || !form.description.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.createIncident(form.title, form.description, form.severity);
      setForm({ title: "", description: "", severity: "medium" });
      await load();
      onSelect(created.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      {error && (
        <div className="error-banner">
          <span>⚠</span> {error}
        </div>
      )}

      {/* ── Report form (collapsible) ── */}
      <div className="panel">
        <button
          className="collapsible-header"
          onClick={() => setFormOpen((o) => !o)}
          aria-expanded={formOpen}
          style={{ width: "100%", background: "none", border: "none", color: "inherit" }}
        >
          <span className="panel-label" style={{ marginBottom: 0 }}>Report incident</span>
          <span className={`collapsible-toggle ${formOpen ? "open" : ""}`}>▼</span>
        </button>

        {formOpen && (
          <div className="collapsible-body">
            <form id="report-form" onSubmit={handleSubmit}>
              <label className="field-label" htmlFor="inc-title">Title</label>
              <input
                id="inc-title"
                placeholder="e.g. Login endpoint returns 500"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />

              <label className="field-label" htmlFor="inc-desc">Description</label>
              <span className="field-sublabel">Include the endpoint, error, and anything you've already noticed.</span>
              <textarea
                id="inc-desc"
                placeholder="What's happening?"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />

              <label className="field-label" htmlFor="inc-severity">Severity</label>
              <select
                id="inc-severity"
                value={form.severity}
                onChange={(e) => setForm({ ...form, severity: e.target.value })}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>

              <button
                className="btn btn-primary"
                type="submit"
                disabled={submitting}
                style={{ width: "100%" }}
              >
                {submitting ? "Reporting…" : "Report incident"}
              </button>
            </form>
          </div>
        )}
      </div>

      {/* ── Incident list ── */}
      <div className="incident-list-section">
        <div className="incident-list-header">
          Incidents ({incidents.length})
        </div>

        {incidents.length === 0 ? (
          <p className="text-muted text-small" style={{ padding: "12px 4px" }}>
            No incidents yet.
          </p>
        ) : (
          incidents.map((incident) => (
            <button
              key={incident.id}
              className={`incident-item ${selectedId === incident.id ? "selected" : ""}`}
              onClick={() => onSelect(incident.id)}
            >
              <span className="incident-item-title">{incident.title}</span>
              <span className="incident-item-meta">
                <StatusPill status={incident.status} />
                <span className="text-mono" style={{ fontSize: 10.5 }}>
                  {new Date(incident.created_at).toLocaleDateString()}
                </span>
              </span>
            </button>
          ))
        )}
      </div>
    </>
  );
}
