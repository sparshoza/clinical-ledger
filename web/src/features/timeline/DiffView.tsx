import type { DiffOut } from "../../api/types";

const VERBS: Record<string, string> = {
  add: "Added",
  remove: "Removed",
  replace: "Changed",
  move: "Moved",
  copy: "Copied",
  binary: "File changed",
};

/** What changed between two versions, as a ruled list of operations. */
export function DiffView({ diff }: { diff: DiffOut }) {
  if (diff.ops.length === 0) {
    return <p className="text-ink-2 text-sm">No changes between these versions.</p>;
  }
  return (
    <ul className="text-sm">
      {diff.ops.map((op, index) => {
        const verb = VERBS[String(op.op)] ?? String(op.op);
        return (
          <li key={index} className="ledger-rule grid grid-cols-[6.5rem_1fr] gap-2 py-1">
            <span className="font-semibold">{verb}</span>
            <span className="min-w-0">
              <code className="break-all">{String(op.path ?? "")}</code>
              {"value" in op && (
                <code className="text-ink-2 mt-0.5 block break-all">
                  {JSON.stringify(op.value)}
                </code>
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
