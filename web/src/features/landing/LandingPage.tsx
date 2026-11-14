import { useState } from "react";
import { useEvents, useStats } from "../../api/hooks";
import { useSession } from "../../api/session";
import type { VerifyOut } from "../../api/types";
import { Landing } from "./Landing";
import { LivePreview } from "./LivePreview";

/** The landing page wired to the visitor's own ledger. The same session carries into /demo. */
export function LandingPage() {
  const { call, error } = useSession();
  const stats = useStats();
  const events = useEvents(null);
  const [verifying, setVerifying] = useState(false);
  const [result, setResult] = useState<VerifyOut | null>(null);

  return (
    <Landing
      preview={
        <LivePreview
          stats={stats.data ?? null}
          events={events.data?.items ?? []}
          verifying={verifying}
          result={result}
          error={error && error.status < 500 ? { title: error.problem.title, detail: error.problem.detail } : null}
          onVerify={() => {
            setVerifying(true);
            call<VerifyOut>("/verify", { method: "POST", body: {} })
              .then(setResult)
              .catch(() => setResult(null))
              .finally(() => setVerifying(false));
          }}
        />
      }
    />
  );
}
