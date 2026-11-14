import { useState } from "react";
import { shortHash } from "../lib/format";
import { CopyIcon } from "./icons";

/** A short hash that copies the full value. The full hash is the accessible name. */
export function HashText({ hash, copyable = false }: { hash: string; copyable?: boolean }) {
  const [copied, setCopied] = useState(false);
  if (!copyable || !hash) {
    return (
      <span className="mono" title={hash}>
        {shortHash(hash)}
      </span>
    );
  }
  return (
    <button
      type="button"
      className="mono inline-flex items-center gap-1 rounded-[3px] px-1 hover:bg-paper-2"
      title={hash}
      aria-label={copied ? "Copied" : `Copy hash ${hash}`}
      onClick={() => {
        void navigator.clipboard?.writeText(hash).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        });
      }}
    >
      {shortHash(hash)}
      <span className="text-ink-2">
        <CopyIcon />
      </span>
    </button>
  );
}
