import { Fragment } from "react";
import type { EventOut } from "../../api/types";
import { HashText } from "../../components/HashText";
import { BrokenIcon } from "../../components/icons";
import { eventLabel, formatTime } from "../../lib/format";

type Props = {
  events: EventOut[];
  brokenSeq: number | null;
  /** The hash the ledger holds at the broken entry, and the one recomputed from its fields. */
  mismatch?: { stored: string; computed: string } | null;
};

// When, By and Carried from fold away on phones; No., Entry and Hash carry the story.
const WIDE = "hidden sm:table-cell";

/** The journal: newest entries first, each carrying the previous entry's hash forward. */
export function AuditLog({ events, brokenSeq, mismatch = null }: Props) {
  const hasNewer = brokenSeq !== null && events.some((e) => e.seq > brokenSeq);
  return (
    <div className="overflow-x-auto">
      <table aria-label="Journal" className="w-full border-collapse text-sm">
        <thead>
          <tr className="ledger-head text-ink-2 text-left text-xs whitespace-nowrap">
            <th scope="col" className="py-1 pr-2 font-medium">No.</th>
            <th scope="col" className={`${WIDE} py-1 pr-2 font-medium`}>When</th>
            <th scope="col" className="py-1 pr-2 font-medium">Entry</th>
            <th scope="col" className={`${WIDE} py-1 pr-2 font-medium`}>By</th>
            <th scope="col" className="py-1 pr-2 font-medium">Hash</th>
            <th scope="col" className={`${WIDE} py-1 font-medium`}>Carried from</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => {
            const broken = brokenSeq !== null && event.seq === brokenSeq;
            const unverified = brokenSeq !== null && event.seq > brokenSeq;
            return (
              <Fragment key={event.seq}>
                {broken && hasNewer && (
                  <tr>
                    <td colSpan={6} className="text-alarm pt-2 pb-1 text-xs font-semibold">
                      Entries above were written after the break and cannot be trusted until the
                      ledger is reset.
                    </td>
                  </tr>
                )}
                <tr
                  className={`align-baseline ${
                    broken ? "bg-alarm-paper text-alarm" : unverified ? "unverified ledger-rule" : "ledger-rule"
                  }`}
                >
                  <td className={`py-1 pr-2 font-semibold ${broken ? "line-through" : ""}`}>
                    {event.seq}
                  </td>
                  <td className={`${WIDE} py-1 pr-2 whitespace-nowrap`}>
                    {formatTime(event.occurred_at)}
                  </td>
                  <td className="py-1 pr-2">
                    {eventLabel(event.event_type)}
                    {event.version_no ? (
                      <span className="text-ink-2"> v{event.version_no}</span>
                    ) : null}
                  </td>
                  <td className={`${WIDE} py-1 pr-2`}>{event.actor_role}</td>
                  <td className="py-1 pr-2 whitespace-nowrap">
                    {broken && mismatch ? (
                      <span className="grid gap-0.5">
                        <span className="text-ink-2 line-through">
                          <span className="sr-only">Stored </span>
                          <HashText hash={mismatch.stored} />
                        </span>
                        <span className="font-semibold">
                          <span className="text-xs font-normal">Recomputed </span>
                          <HashText hash={mismatch.computed} />
                        </span>
                      </span>
                    ) : (
                      <HashText hash={event.event_hash} />
                    )}
                  </td>
                  <td className={`${WIDE} text-ink-2 py-1 whitespace-nowrap`}>
                    <HashText hash={event.prev_hash} />
                  </td>
                </tr>
                {broken && (
                  <tr className="ledger-rule bg-alarm-paper text-alarm">
                    {/* Its own line, so the stamp never widens a column of the journal. */}
                    <td colSpan={6} className="pb-1 pl-8 sm:pl-10">
                      <span className="stamp flex items-center gap-1 font-semibold whitespace-nowrap">
                        <BrokenIcon />
                        Does not reconcile
                      </span>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
