/** Shown when the API cannot be reached (cold start, outage). Says what happened and what to do. */
export function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="ledger-rule flex flex-wrap items-center gap-4 py-6">
      <div>
        <p className="font-semibold">The server is waking up or unreachable.</p>
        <p className="text-ink-2 text-sm">
          The free hosting tier sleeps when idle. It usually answers within a few seconds.
        </p>
      </div>
      <button type="button" className="btn btn-quiet" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}
