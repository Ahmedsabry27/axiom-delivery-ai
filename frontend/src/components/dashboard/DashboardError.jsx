export default function DashboardError({ onRetry }) {
  return (
    <main className="min-h-full bg-gradient-to-br from-[#071426] via-[#0B1F3A] to-[#142B52] p-5 text-white md:p-8">
      <section className="rounded-2xl border border-red-400/20 bg-red-500/10 p-6 text-red-100 shadow-2xl shadow-black/20">
        <h1 className="text-lg font-semibold">Dashboard data is temporarily unavailable</h1>
        <p className="mt-1 text-sm text-red-200/80">The AI Copilot Operations Center could not load its latest runtime data.</p>
        <button type="button" className="mt-4 rounded-lg bg-red-400/15 px-4 py-2 text-sm font-medium text-red-100 transition hover:bg-red-400/25" onClick={onRetry}>Retry</button>
      </section>
    </main>
  );
}
