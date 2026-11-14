import { useState } from "react";
import type { RecordSummaryOut } from "../../api/types";
import { kindLabel, patientLabel } from "../../lib/format";

type Props = {
  records: RecordSummaryOut[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

/** Patients shown on a phone before the list asks to expand. Wide screens scroll instead. */
const PHONE_PATIENTS = 4;

/** The accounts: records grouped under the synthetic patient they belong to. */
export function RecordList({ records, selectedId, onSelect }: Props) {
  const [expanded, setExpanded] = useState(false);
  const groups = new Map<string, RecordSummaryOut[]>();
  for (const record of records) {
    const key = patientLabel(record.subject_ref);
    groups.set(key, [...(groups.get(key) ?? []), record]);
  }
  const capped = !expanded && groups.size > PHONE_PATIENTS;
  return (
    <nav aria-label="Records">
      <ul className="divide-rule divide-y">
        {[...groups.entries()].map(([patient, items], index) => (
          <li
            key={patient}
            className={`py-2 ${capped && index >= PHONE_PATIENTS ? "max-lg:hidden" : ""}`}
          >
            <p className="text-ink-2 px-2 pb-1 text-xs">{patient}</p>
            <ul>
              {items.map((record) => {
                const selected = record.id === selectedId;
                return (
                  <li key={record.id}>
                    <button
                      type="button"
                      aria-current={selected ? "true" : undefined}
                      onClick={() => onSelect(record.id)}
                      className={`flex w-full items-baseline justify-between gap-2 rounded-[3px] px-2 py-1 text-left text-sm ${
                        selected ? "bg-paper-2 font-semibold" : "hover:bg-paper-2"
                      }`}
                    >
                      <span>{kindLabel(record.kind)}</span>
                      <span className="text-ink-2 text-xs">v{record.latest_version_no}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ul>
      {capped && (
        <button
          type="button"
          aria-expanded="false"
          className="btn btn-quiet mt-2 w-full justify-center lg:hidden"
          onClick={() => setExpanded(true)}
        >
          Show all {groups.size} patients
        </button>
      )}
    </nav>
  );
}
