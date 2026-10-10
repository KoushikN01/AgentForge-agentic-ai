// The ONLY file that knows the API's base URL, endpoint paths, and
// response shapes (see backend/app/api/routes.py and schemas.py) - every
// component calls these functions, never fetch() directly.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `${response.status} ${response.statusText}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  listIncidents: () => request("/incidents"),
  createIncident: (title, description, severity) =>
    request("/incidents", { method: "POST", body: JSON.stringify({ title, description, severity }) }),
  getIncident: (id) => request(`/incidents/${id}`),
  startInvestigation: (id) => request(`/incidents/${id}/investigate`, { method: "POST" }),
  getTimeline: (id) => request(`/incidents/${id}/timeline`),
  approve: (id, approved) =>
    request(`/incidents/${id}/approve`, { method: "POST", body: JSON.stringify({ approved }) }),
};

// Statuses for which the workflow is still running, so the UI should
// keep polling (mirrors app/models/incident_state.IncidentStatus).
export const IN_PROGRESS_STATUSES = new Set(["new", "in_progress"]);
