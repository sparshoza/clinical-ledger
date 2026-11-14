import type { Role } from "../../api/types";
import { ResetIcon } from "../../components/icons";

export type PendingAction = "add" | "file" | "log" | "reset" | null;

type Props = {
  role: Role;
  pending: PendingAction;
  hasRecord: boolean;
  onAddVersion: () => void;
  onTamperFile: () => void;
  onTamperLog: () => void;
  onReset: () => void;
};

/** The demo's moves. Tampering only touches this visitor's private ledger. */
export function TryItPanel({
  role,
  pending,
  hasRecord,
  onAddVersion,
  onTamperFile,
  onTamperLog,
  onReset,
}: Props) {
  const busy = pending !== null;
  return (
    <section aria-label="Try it" className="border-rule mt-4 flex flex-wrap items-center gap-2 border-t pt-3">
      <h3 className="mr-1 text-sm font-semibold">Try it</h3>
      {role !== "auditor" && (
        <button
          type="button"
          className="btn btn-quiet"
          onClick={onAddVersion}
          disabled={busy || !hasRecord}
        >
          {pending === "add" ? "Adding…" : "Add a version"}
        </button>
      )}
      {role === "admin" ? (
        <>
          <button
            type="button"
            className="btn btn-quiet"
            onClick={onTamperFile}
            disabled={busy}
          >
            Tamper with a file
          </button>
          <button type="button" className="btn btn-quiet" onClick={onTamperLog} disabled={busy}>
            Tamper with the log
          </button>
        </>
      ) : (
        <span className="text-ink-2 text-sm">Switch to admin to tamper with the ledger.</span>
      )}
      <button type="button" className="btn btn-quiet ml-auto" onClick={onReset} disabled={busy}>
        <ResetIcon />
        Reset the demo
      </button>
    </section>
  );
}
