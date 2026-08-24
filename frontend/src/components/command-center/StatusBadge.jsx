const styles = {
  Healthy: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  "On Track": "bg-blue-50 text-blue-700 ring-blue-600/20",
  Warning: "bg-amber-50 text-amber-800 ring-amber-600/20",
  Critical: "bg-red-50 text-red-700 ring-red-600/20",
  High: "bg-red-50 text-red-700 ring-red-600/20",
  Medium: "bg-amber-50 text-amber-800 ring-amber-600/20",
  Low: "bg-slate-100 text-slate-700 ring-slate-500/20",
  Open: "bg-blue-50 text-blue-700 ring-blue-600/20",
  Overdue: "bg-red-50 text-red-700 ring-red-600/20",
};
export default function StatusBadge({ children }) {
  return <span className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${styles[children] || styles.Low}`}>{children}</span>;
}
