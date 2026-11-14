import { lineDiff, type DiffLine } from "../../lib/lineDiff";

type Props = {
  previous: unknown;
  current: unknown;
  previousNo: number;
  currentNo: number;
};

function Column({ title, lines, side }: { title: string; lines: DiffLine[]; side: "before" | "after" }) {
  return (
    <div className="min-w-0">
      <h4 className="text-ink-2 mb-1 text-xs font-semibold">{title}</h4>
      <pre className="bg-paper-2 max-h-[26rem] overflow-auto rounded-[3px] py-2 text-xs leading-relaxed">
        <code className="block">
          {lines.map((line, n) => (
            <span
              key={n}
              data-changed={line.changed ? side : undefined}
              className={`grid grid-cols-[1.25rem_minmax(0,1fr)] pr-3 ${line.changed ? "change-line" : ""}`}
            >
              <span aria-hidden="true" className="text-ink-2 text-center select-none">
                {line.changed ? (side === "before" ? "−" : "+") : ""}
              </span>
              <span className="whitespace-pre-wrap [overflow-wrap:anywhere]">{line.text || " "}</span>
            </span>
          ))}
        </code>
      </pre>
    </div>
  );
}

/** The previous and the selected version at equal width, with changed lines marked on each side. */
export function VersionCompare({ previous, current, previousNo, currentNo }: Props) {
  const { before, after } = lineDiff(JSON.stringify(previous, null, 2), JSON.stringify(current, null, 2));
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Column title={`Version ${previousNo}`} lines={before} side="before" />
      <Column title={`Version ${currentNo}`} lines={after} side="after" />
    </div>
  );
}
