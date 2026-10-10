const LABELS = {
  new: "New",
  in_progress: "Investigating",
  awaiting_approval: "Awaiting approval",
  resolved: "Resolved",
  failed: "Failed",
};

export default function StatusPill({ status }) {
  return <span className={`pill ${status}`}>{LABELS[status] || status}</span>;
}
