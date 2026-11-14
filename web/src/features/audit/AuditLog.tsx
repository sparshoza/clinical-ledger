import type { EventOut } from "../../api/types";
import { HashText } from "../../components/HashText";
import { BrokenIcon } from "../../components/icons";
import { eventLabel, formatTime } from "../../lib/format";

type Props = {
  events: EventOut[];
  brokenSeq: number | null;
};

/** The journal: newest entries first, each carrying the previous entry's hash forward. */
export function AuditLog({ events, brokenSeq }: Props) {
  return (
    <div className="overflow-x-auto">
      <table aria-label="Journal" className="w-full border-collapse text-sm">
        <thead>
          <tr className="ledger-head text-ink-2 text-left text-xs whitespace-nowrap">
            <th scope="col" className="py-1 pr-2 font-medium">No.</th>
            <th scope="col" className="py-1 pr-2 font-medium">When</th>
            <th scope="col" className="py-1 pr-2 font-medium">Entry</th>
            <th scope="col" className="py-1 pr-2 font-medium">By</th>
            <th scope="col" className="py-1 pr-2 font-medium">Hash</th>
            <th scope="col" className="py-1 font-medium">Carried from</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => {
            const broken = brokenSeq !== null && event.seq === brokenSeq;
            const unverified = brokenSeq !== null && event.seq > brokenSeq;
            return (
              <tr
                key={event.seq}
                className={`ledger-rule align-baseline ${
                  broken ? "bg-alarm-paper text-alarm" : unverified ? "text-ink-2" : ""
                }`}
              >
                <td className={`py-1 pr-2 font-semibold ${broken ? "line-through" : ""}`}>
                  {event.seq}
                </td>
                <td className="py-1 pr-2 whitespace-nowrap">{formatTime(event.occurred_at)}</td>
                <td className="py-1 pr-2">
                  {eventLabel(event.event_type)}
                  {event.version_no ? <span className="text-ink-2"> v{event.version_no}</span> : null}
                  {broken && (
                    <span className="flex items-center gap-1 font-semibold">
                      <BrokenIcon />
                      Does not reconcile
                    </span>
                  )}
                </td>
                <td className="py-1 pr-2">{event.actor_role}</td>
                <td className="py-1 pr-2 whitespace-nowrap">
                  <HashText hash={event.event_hash} />
                </td>
                <td className="text-ink-2 py-1 whitespace-nowrap">
                  <HashText hash={event.prev_hash} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
