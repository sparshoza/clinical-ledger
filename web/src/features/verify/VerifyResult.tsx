import type { VerifyOut } from "../../api/types";
import { BalancedIcon, BrokenIcon } from "../../components/icons";

type Props = {
  result: VerifyOut | null;
  tampered: "file" | "log" | null;
};

/** What the last verification found, stated as a sentence with an icon, never colour alone. */
export function VerifyResult({ result, tampered }: Props) {
  if (!result) {
    if (!tampered) return null;
    return (
      <p role="status" className="bg-paper-2 rounded-[3px] px-3 py-2 text-sm">
        {tampered === "log"
          ? "One journal entry was quietly edited. Run Verify the chain to see whether it is caught."
          : "One stored file was quietly altered. Run Verify the chain to see whether it is caught."}
      </p>
    );
  }
  if (result.ok) {
    return (
      <p role="status" className="text-reconciled inline-flex items-center gap-2 py-2 text-sm font-semibold">
        <BalancedIcon />
        Chain intact: {result.checked_events} entries and {result.checked_blobs} files checked.
      </p>
    );
  }
  return (
    <div role="alert" className="bg-alarm-paper text-alarm rounded-[3px] px-3 py-2 text-sm">
      <p className="inline-flex items-center gap-2 font-semibold">
        <BrokenIcon />
        {result.reason === "blob_mismatch"
          ? "A stored file no longer matches its hash."
          : `Broken at entry #${result.first_broken_seq}: ${
              result.reason === "broken_link" ? "broken link" : "hash mismatch"
            }.`}
      </p>
      <p className="mt-1">
        {result.reason === "blob_mismatch"
          ? "Its content address was recorded when it was written, so any change to the bytes shows up."
          : "Recomputing that entry's hash no longer gives the value the next entry carried forward."}{" "}
        Reset the demo to start again.
      </p>
    </div>
  );
}
