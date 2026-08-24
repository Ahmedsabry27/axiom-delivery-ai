import { useEffect } from "react";
import { isRouteErrorResponse, useRouteError } from "react-router-dom";

import { isStaleChunkError } from "./staleChunkRecovery";

const RECOVERY_KEY = "axiom:chunk-recovery";
const RECOVERY_WINDOW_MS = 30_000;

export default function RouteErrorPage() {
  const error = useRouteError();
  const staleChunk = isStaleChunkError(error);

  useEffect(() => {
    if (!staleChunk) return;
    const lastRecovery = Number(window.sessionStorage.getItem(RECOVERY_KEY) || 0);
    if (Date.now() - lastRecovery > RECOVERY_WINDOW_MS) {
      window.sessionStorage.setItem(RECOVERY_KEY, String(Date.now()));
      window.location.reload();
    }
  }, [staleChunk]);

  const message = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : error instanceof Error
      ? error.message
      : "The requested page could not be loaded.";

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#faf8f5] p-6 text-stone-900">
      <section className="w-full max-w-xl border border-stone-300 bg-white p-8 text-center shadow-sm">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#a00028]">Axiom Delivery AI</p>
        <h1 className="mt-3 font-display text-3xl font-bold">
          {staleChunk ? "Updating to the latest version" : "This page could not be loaded"}
        </h1>
        <p className="mt-4 text-sm leading-6 text-stone-600">
          {staleChunk
            ? "A newer deployment is available. The application is refreshing once to load the current version."
            : message}
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="mt-6 rounded-xl bg-[#a00028] px-4 py-2.5 text-sm font-semibold text-white"
        >
          Reload application
        </button>
      </section>
    </main>
  );
}
