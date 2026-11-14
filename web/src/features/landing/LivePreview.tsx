import type { EventOut, StatsOut, VerifyOut } from "../../api/types";
import { HashText } from "../../components/HashText";
import { BalancedIcon, BrokenIcon } from "../../components/icons";
import { eventLabel } from "../../lib/format";
import { DEMO_PATH } from "../../lib/links";

type Props = {
  stats: StatsOut | null;
  events: EventOut[];
  onVerify: () => void;
  verifying: boolean;
  result: VerifyOut | null;
};

/** The visitor's own ledger, live: the newest journal entries and a working Verify. */
export function LivePreview({ stats, events, onVerify, verifying, result }: Props) {
  return (
    <section aria-labelledby="live" className="border-rule bg-surface rounded-md border p-4 sm:p-5">
      <h2 id="live" className="text-base font-semibold">
        Your ledger, live
      </h2>
      {stats ? (
        <>
          <p className="text-ink-2 mt-1 text-sm">
            Created for you just now and private to this browser. It holds{" "}
            <span className="text-ink font-semibold">{stats.events} entries</span> across{" "}
            {stats.records} records, and expires in 24 hours.
          </p>
          <table aria-label="Newest journal entries" className="mt-4 w-full border-collapse text-sm">
            <thead>
              <tr className="ledger-head text-ink-2 text-left text-xs">
                <th scope="col" className="py-1 pr-2 font-medium">No.</th>
                <th scope="col" className="py-1 pr-2 font-medium">Entry</th>
                <th scope="col" className="py-1 text-right font-medium">Hash</th>
              </tr>
            </thead>
            <tbody>
              {events.slice(0, 7).map((event) => (
                <tr key={event.seq} className="ledger-rule align-baseline">
                  <td className="py-1 pr-2 font-semibold">{event.seq}</td>
                  <td className="py-1 pr-2">
                    {eventLabel(event.event_type)}
                    {event.version_no ? <span className="text-ink-2"> v{event.version_no}</span> : null}
                  </td>
                  <td className="py-1 text-right">
                    <HashText hash={event.event_hash} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button type="button" className="btn btn-primary" onClick={onVerify} disabled={verifying}>
              {verifying ? "Verifying…" : "Verify the chain"}
            </button>
            <a className="btn btn-quiet" href={DEMO_PATH}>
              Open the demo
            </a>
          </div>
          <div aria-live="polite" className="mt-3 min-h-6 text-sm">
            {result?.ok === true && (
              <p className="text-reconciled inline-flex items-center gap-2 font-semibold">
                <BalancedIcon />
                Chain intact: every one of {result.checked_events} entries and {result.checked_blobs}{" "}
                files check out.
              </p>
            )}
            {result?.ok === false && (
              <p className="text-alarm inline-flex items-center gap-2 font-semibold">
                <BrokenIcon />
                Broken{result.first_broken_seq ? ` at entry #${result.first_broken_seq}` : ""}. Open the
                demo to see where.
              </p>
            )}
          </div>
        </>
      ) : (
        <p className="text-ink-2 mt-2 text-sm">
          Creating your private ledger. The free database sleeps when nobody is using it, so the
          first visit can take a few seconds.
        </p>
      )}
    </section>
  );
}
