import { useState } from "react";
import Dashboard from "./components/Dashboard.jsx";
import IncidentDetail from "./components/IncidentDetail.jsx";

export default function App() {
  const [selectedId, setSelectedId] = useState(null);

  return (
    <>
      {/* ── Sticky top bar ── */}
      <header className="app-header">
        <div className="header-brand">
          <span className="app-logo">
            Agent<span className="forge">Forge</span>
          </span>
          <span className="app-tagline">AI incident investigation console</span>
        </div>

        <div className="status-bar">
          <div className="status-dot ok">
            <span className="status-name">API</span>
            <span className="status-value">connected</span>
          </div>
          <div className="status-dot">
            <span className="status-name">Mode</span>
            <span className="status-value">multi-agent</span>
          </div>
        </div>
      </header>

      {/* ── Two-column layout ── */}
      <div className="layout">
        {/* Left sidebar — incident list + report form */}
        <aside className="sidebar">
          <Dashboard onSelect={setSelectedId} selectedId={selectedId} />
        </aside>

        {/* Right main area — incident detail */}
        <main className="main-content">
          {selectedId ? (
            <IncidentDetail
              incidentId={selectedId}
              onBack={() => setSelectedId(null)}
            />
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon">🔍</div>
              <h2>No incident selected</h2>
              <p>
                Report a new incident using the form on the left, or select an
                existing one to begin investigation.
              </p>
            </div>
          )}
        </main>
      </div>
    </>
  );
}
