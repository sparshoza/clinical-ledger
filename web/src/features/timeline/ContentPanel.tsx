import type { Role } from "../../api/types";
import { BrokenIcon } from "../../components/icons";

type Props = {
  role: Role;
  content: unknown;
  loading: boolean;
  error: { status: number; title: string } | null;
};

/** The document as stored at the chosen version. Every read here is itself written to the journal. */
export function ContentPanel({ role, content, loading, error }: Props) {
  if (role === "auditor") {
    return (
      <p className="bg-paper-2 rounded-[3px] p-3 text-sm">
        Auditors can see the log but not record content.
      </p>
    );
  }
  if (error?.status === 409) {
    return (
      <div role="alert" className="bg-alarm-paper text-alarm rounded-[3px] p-3 text-sm">
        <p className="inline-flex items-center gap-1 font-semibold">
          <BrokenIcon /> {error.title}
        </p>
        <p className="mt-1">
          The bytes in storage no longer hash to the value the ledger recorded, so the
          content was refused instead of shown.
        </p>
      </div>
    );
  }
  if (error) {
    // Not a failed hash check, so not alarm red: red means the ledger does not reconcile.
    return (
      <div role="alert" className="bg-paper-2 rounded-[3px] p-3 text-sm">
        <p className="font-semibold">{error.title}</p>
        <p className="text-ink-2 mt-1">Pick the record again, or reload the page.</p>
      </div>
    );
  }
  if (loading) {
    return <p className="text-ink-2 p-3 text-sm">Reading the stored document…</p>;
  }
  return (
    <pre className="bg-paper-2 max-h-[26rem] overflow-auto rounded-[3px] p-3 text-xs leading-relaxed">
      <code>{JSON.stringify(content, null, 2)}</code>
    </pre>
  );
}
