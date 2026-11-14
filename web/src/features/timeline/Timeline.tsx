import type { VersionOut } from "../../api/types";
import { formatDate } from "../../lib/format";
import { HashText } from "../../components/HashText";

type Props = {
  versions: VersionOut[];
  selected: number;
  onSelect: (versionNo: number) => void;
};

/** The folio: every version as a ruled entry, plus a slider to read the record as of any version. */
export function Timeline({ versions, selected, onSelect }: Props) {
  const latest = versions.at(-1)?.version_no ?? 1;
  const current = versions.find((v) => v.version_no === selected);
  return (
    <div>
      <ol className="mb-3">
        {versions.map((version) => {
          const isLatest = version.version_no === latest;
          const isSelected = version.version_no === selected;
          return (
            <li key={version.version_no} className="ledger-rule">
              <button
                type="button"
                aria-current={isSelected ? "true" : undefined}
                aria-label={`Version ${version.version_no}${isLatest ? ", latest" : ""}`}
                onClick={() => onSelect(version.version_no)}
                className={`grid w-full grid-cols-[2.5rem_6.5rem_1fr_auto] items-baseline gap-2 px-1 py-1.5 text-left text-sm ${
                  isSelected ? "bg-paper-2" : "hover:bg-paper-2"
                }`}
              >
                <span className="font-semibold">v{version.version_no}</span>
                <span className="text-ink-2">{formatDate(version.created_at)}</span>
                <span className="truncate">
                  {version.note || "No note"}
                  {isLatest && <span className="text-ink-2"> (latest)</span>}
                </span>
                <HashText hash={version.content_hash} />
              </button>
            </li>
          );
        })}
      </ol>
      <label className="flex items-center gap-3 text-sm">
        <span className="text-ink-2 shrink-0">As of</span>
        <input
          type="range"
          className="w-full"
          min={1}
          max={latest}
          step={1}
          value={selected}
          aria-label="Show the record as of"
          aria-valuemin={1}
          aria-valuemax={latest}
          aria-valuenow={selected}
          aria-valuetext={
            current ? `Version ${current.version_no}, ${formatDate(current.created_at)}` : undefined
          }
          onChange={(event) => onSelect(Number(event.target.value))}
        />
        <span className="w-24 shrink-0 text-right">
          {current ? formatDate(current.created_at) : ""}
        </span>
      </label>
    </div>
  );
}
