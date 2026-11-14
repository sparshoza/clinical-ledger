import { useEffect, useMemo, useState } from "react";
import { ApiError } from "./api/client";
import { useDiff, useEvents, useRecordVersion, useRecords, useStats, useVersions } from "./api/hooks";
import { useSession } from "./api/session";
import type { VerifyOut } from "./api/types";
import { AuditLog } from "./features/audit/AuditLog";
import { RecordList } from "./features/records/RecordList";
import { ErrorState } from "./features/status/ErrorState";
import { StatusBar } from "./features/status/StatusBar";
import { ContentPanel } from "./features/timeline/ContentPanel";
import { DiffView } from "./features/timeline/DiffView";
import { Timeline } from "./features/timeline/Timeline";
import { VersionCompare } from "./features/timeline/VersionCompare";
import { kindLabel, patientLabel } from "./lib/format";

const REPO_URL = "https://github.com/sparshoza/clinical-ledger";
const PORTFOLIO_URL = "https://github.com/sparshoza";

type Props = {
  /** Slot for the role switcher (header) and the try-it actions (folio). */
  header?: React.ReactNode;
  actions?: (recordId: string | null) => React.ReactNode;
  verifyResult?: VerifyOut | null;
  onVerify?: () => void;
  verifying?: boolean;
  busy?: boolean;
};

export function App({
  header,
  actions,
  verifyResult = null,
  onVerify,
  verifying = false,
  busy = false,
}: Props) {
  const { session, error: sessionError, retry } = useSession();
  const stats = useStats();
  const records = useRecords();
  const brokenSeq =
    verifyResult?.ok === false ? (verifyResult.first_broken_seq ?? null) : null;
  const [showLatest, setShowLatest] = useState(false);
  useEffect(() => setShowLatest(false), [brokenSeq]);
  const focusSeq = brokenSeq !== null && !showLatest ? brokenSeq : null;
  const events = useEvents(focusSeq);
  const [recordId, setRecordId] = useState<string | null>(null);
  const versions = useVersions(recordId);
  const [versionNo, setVersionNo] = useState<number | null>(null);

  const items = useMemo(() => records.data?.items ?? [], [records.data]);
  const latest = versions.data?.items.at(-1)?.version_no ?? null;
  const shown = versionNo ?? latest;
  const content = useRecordVersion(recordId, shown);
  const previousNo = shown && shown > 1 ? shown - 1 : null;
  const previous = useRecordVersion(recordId, previousNo);
  const diff = useDiff(recordId, previousNo, shown);

  useEffect(() => {
    if (recordId === null && items[0]) setRecordId(items[0].id);
  }, [items, recordId]);
  useEffect(() => setVersionNo(null), [recordId, session?.tenant_id]);
  useEffect(() => {
    if (session && recordId && !items.some((r) => r.id === recordId) && items[0]) {
      setRecordId(items[0].id);
    }
  }, [items, recordId, session]);

  const role = session?.role ?? "admin";
  const selected = items.find((r) => r.id === recordId) ?? null;
  const unreachable =
    sessionError !== null ||
    [stats.error, records.error, events.error].some(
      (e) => e instanceof ApiError && e.status >= 500,
    );
  const problemOf = (error: unknown) =>
    error instanceof ApiError ? { status: error.status, title: error.problem.title } : null;
  const contentError = problemOf(content.error);
  const previousError = problemOf(previous.error);
  const mismatch =
    verifyResult?.stored_hash && verifyResult.computed_hash
      ? { stored: verifyResult.stored_hash, computed: verifyResult.computed_hash }
      : null;
  const docOf = (data: typeof content.data) => data?.content_json ?? data?.content_b64 ?? null;

  return (
    <div className="mx-auto flex min-h-dvh max-w-[96rem] flex-col px-4 sm:px-6">
      <header className="flex flex-wrap items-center gap-x-5 gap-y-2 pt-4 pb-2">
        <h1 className="text-xl font-semibold tracking-tight">Clinical Ledger</h1>
        <p className="text-ink-2 text-sm">
          A tamper-evident record book. All data is synthetic (Synthea).
        </p>
        <nav aria-label="About this project" className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          <a href={REPO_URL}>Source on GitHub</a>
          <a href={`${REPO_URL}/blob/main/docs/benchmarks.md`}>Benchmarks</a>
          <a href={PORTFOLIO_URL}>Sparsh Oza</a>
        </nav>
        <div className="ml-auto flex items-center gap-4">{header}</div>
      </header>

      {unreachable ? (
        <ErrorState
          onRetry={() => {
            retry();
            void stats.refetch();
            void records.refetch();
            void events.refetch();
          }}
        />
      ) : stats.data ? (
        <StatusBar
          stats={stats.data}
          onVerify={() => onVerify?.()}
          canVerify={role !== "clinician"}
          verifying={verifying}
          busy={busy}
        />
      ) : (
        <p className="ledger-head text-ink-2 py-3 text-sm">Opening your private ledger…</p>
      )}

      <main className="grid flex-1 gap-x-8 gap-y-6 py-5 lg:grid-cols-[14rem_minmax(0,1fr)_minmax(0,30rem)]">
        <section aria-labelledby="accounts" className="order-3 lg:order-1">
          <h2 id="accounts" className="ledger-head pb-1 font-semibold">
            Records
          </h2>
          {records.isPending ? (
            <p className="text-ink-2 py-2 text-sm">Loading records…</p>
          ) : (
            <div className="lg:max-h-[calc(100dvh-12rem)] lg:overflow-y-auto">
              <RecordList records={items} selectedId={recordId} onSelect={setRecordId} />
            </div>
          )}
        </section>

        <section aria-labelledby="folio" className="order-1 min-w-0 lg:order-2">
          <h2 id="folio" className="ledger-head flex items-baseline gap-2 pb-1 font-semibold">
            {selected ? (
              <>
                {kindLabel(selected.kind)}
                <span className="text-ink-2 text-sm font-normal">
                  {patientLabel(selected.subject_ref)}
                </span>
              </>
            ) : (
              "Record"
            )}
          </h2>
          <p className="text-ink-2 py-2 text-sm">
            Every change is a new version. Nothing is overwritten, and every read is written to
            the journal.
          </p>
          {versions.data && shown !== null && (
            <Timeline versions={versions.data.items} selected={shown} onSelect={setVersionNo} />
          )}
          {actions?.(recordId)}
          <div className="mt-5">
            {role === "auditor" || previousNo === null || contentError || previousError ? (
              <>
                <h3 className="mb-2 text-sm font-semibold">
                  Stored document{shown ? `, version ${shown}` : ""}
                </h3>
                <ContentPanel
                  role={role}
                  content={docOf(content.data)}
                  loading={content.isPending && role !== "auditor"}
                  error={contentError ?? previousError}
                />
              </>
            ) : (
              <>
                <h3 className="mb-2 text-sm font-semibold">
                  Version {shown} against version {previousNo}
                </h3>
                {content.data && previous.data ? (
                  <VersionCompare
                    previous={docOf(previous.data)}
                    current={docOf(content.data)}
                    previousNo={previousNo}
                    currentNo={shown ?? previousNo + 1}
                  />
                ) : (
                  <p className="text-ink-2 text-sm">Reading both versions…</p>
                )}
                <h3 className="mt-5 mb-2 text-sm font-semibold">Changes, field by field</h3>
                {diff.data ? (
                  <DiffView diff={diff.data} />
                ) : (
                  <p className="text-ink-2 text-sm">Comparing…</p>
                )}
              </>
            )}
          </div>
        </section>

        <section aria-labelledby="journal" className="order-2 min-w-0 lg:order-3">
          <h2 id="journal" className="ledger-head pb-1 font-semibold">
            Journal
          </h2>
          <p className="text-ink-2 py-2 text-sm">
            Each entry's hash covers the one before it, so changing any entry breaks every link
            after it.
          </p>
          {brokenSeq !== null && (
            <p className="flex flex-wrap items-center gap-2 pb-2 text-sm">
              {focusSeq !== null ? (
                <>
                  <span>Showing the entries around #{brokenSeq}.</span>
                  <button type="button" className="text-action underline underline-offset-2" onClick={() => setShowLatest(true)}>
                    Show the latest entries
                  </button>
                </>
              ) : (
                <button type="button" className="text-action underline underline-offset-2" onClick={() => setShowLatest(false)}>
                  Go to entry #{brokenSeq}
                </button>
              )}
            </p>
          )}
          {events.data ? (
            <div className="lg:max-h-[calc(100dvh-14rem)] lg:overflow-y-auto">
              <AuditLog events={events.data.items} brokenSeq={brokenSeq} mismatch={mismatch} />
            </div>
          ) : (
            <p className="text-ink-2 text-sm">Loading entries…</p>
          )}
        </section>
      </main>

      <footer className="border-rule text-ink-2 flex flex-wrap gap-x-5 gap-y-1 border-t py-4 text-sm">
        <span>Records are synthetic, generated with Synthea. No real patient data.</span>
        <a href="/api/docs">API reference</a>
      </footer>
    </div>
  );
}
