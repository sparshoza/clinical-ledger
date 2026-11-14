export type Reason = { title: string; detail?: string | null };

type Props = {
  onRetry: () => void;
  /** The server's own explanation, when it gave one (for example a usage limit). */
  reason?: Reason | null;
};

/** Shown when the API cannot be reached (cold start, outage) or refuses with a reason. */
export function ErrorState({ onRetry, reason = null }: Props) {
  return (
    <div role="alert" className="ledger-rule flex flex-wrap items-center gap-4 py-6">
      <div>
        <p className="font-semibold">{reason?.title ?? "The server is waking up or unreachable."}</p>
        <p className="text-ink-2 text-sm">
          {reason
            ? reason.detail
            : "The free hosting tier sleeps when idle. It usually answers within a few seconds."}
        </p>
      </div>
      <button type="button" className="btn btn-quiet" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}
