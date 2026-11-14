import type { StatsOut } from "../../api/types";
import { HashText } from "../../components/HashText";
import { BalancedIcon, BrokenIcon } from "../../components/icons";
import { formatRelative } from "../../lib/format";

type Props = {
  stats: StatsOut;
  onVerify: () => void;
  canVerify: boolean;
  verifying: boolean;
  /** Another action is running; verifying now would check a ledger that is about to change. */
  busy?: boolean;
};

/** The balance line: where the chain stands right now, and the one check that matters. */
export function StatusBar({ stats, onVerify, canVerify, verifying, busy = false }: Props) {
  const last = stats.last_verify;
  return (
    <section
      aria-label="Chain status"
      className="ledger-head flex flex-wrap items-center gap-x-6 gap-y-2 py-3"
    >
      <div className="flex items-baseline gap-2">
        <span className="text-ink-2 text-sm">Carried forward</span>
        <HashText hash={stats.head_hash} copyable />
      </div>
      <div className="text-sm">
        <span className="font-semibold">{stats.events.toLocaleString("en-US")} entries</span>
        <span className="text-ink-2">
          {" "}
          in {stats.records} records, {stats.versions} versions
        </span>
      </div>
      <div className="text-sm" aria-live="polite">
        {last === null || last === undefined ? (
          <span className="text-ink-2">Not verified yet</span>
        ) : last.ok ? (
          <span className="text-reconciled inline-flex items-center gap-1">
            <BalancedIcon /> Balanced, checked {formatRelative(last.at)}
          </span>
        ) : (
          <span className="text-alarm inline-flex items-center gap-1 font-semibold">
            <BrokenIcon /> Did not reconcile, checked {formatRelative(last.at)}
          </span>
        )}
      </div>
      <div className="ml-auto flex items-center gap-3">
        {!canVerify && (
          <span className="text-ink-2 text-sm">Switch to auditor or admin to verify.</span>
        )}
        <button
          type="button"
          className="btn btn-primary"
          onClick={onVerify}
          disabled={!canVerify || verifying || busy}
        >
          {verifying ? "Verifying…" : "Verify the chain"}
        </button>
      </div>
    </section>
  );
}
