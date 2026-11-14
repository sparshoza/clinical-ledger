import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { App } from "./App";
import { useSession } from "./api/session";
import type { Role, SessionOut, TamperOut, VerifyOut, VersionOut } from "./api/types";
import { TryItPanel, type PendingAction } from "./features/actions/TryItPanel";
import { RoleSwitcher } from "./features/role/RoleSwitcher";
import { VerifyResult } from "./features/verify/VerifyResult";

/** The page: read views plus the demo's actions, verification and role switching. */
export function Console() {
  const { session, call, signIn, adopt } = useSession();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<PendingAction>(null);
  const [verifying, setVerifying] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [result, setResult] = useState<VerifyOut | null>(null);
  const [tampered, setTampered] = useState<"file" | "log" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const refresh = () => queryClient.invalidateQueries({ queryKey: [session?.tenant_id] });

  async function run(kind: Exclude<PendingAction, null>, task: () => Promise<void>) {
    setPending(kind);
    setActionError(null);
    try {
      await task();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "That did not work. Try again.");
    } finally {
      setPending(null);
    }
  }

  const role: Role = session?.role ?? "admin";

  return (
    <App
      header={
        <RoleSwitcher
          role={role}
          busy={switching}
          onChange={(next) => {
            setSwitching(true);
            signIn(next)
              .then(() => setResult(null))
              .catch(() => setActionError("Could not switch role. Try again."))
              .finally(() => setSwitching(false));
          }}
        />
      }
      verifyResult={result}
      verifying={verifying}
      busy={pending !== null || switching}
      onVerify={() => {
        setVerifying(true);
        setActionError(null);
        call<VerifyOut>("/verify", { method: "POST", body: {} })
          .then((verified) => {
            setResult(verified);
            return refresh();
          })
          .catch(() => setActionError("Verification could not run. Try again."))
          .finally(() => setVerifying(false));
      }}
      actions={(recordId) => (
        <>
          <TryItPanel
            role={role}
            pending={pending}
            hasRecord={recordId !== null}
            onAddVersion={() =>
              run("add", async () => {
                await call<VersionOut>(`/records/${recordId}/demo-edit`, { method: "POST" });
                await refresh();
              })
            }
            onTamperFile={() =>
              run("file", async () => {
                await call<TamperOut>("/demo/tamper", { method: "POST", body: { mode: "blob" } });
                setResult(null);
                setTampered("file");
                await refresh();
              })
            }
            onTamperLog={() =>
              run("log", async () => {
                await call<TamperOut>("/demo/tamper", { method: "POST", body: { mode: "event" } });
                setResult(null);
                setTampered("log");
                await refresh();
              })
            }
            onReset={() =>
              run("reset", async () => {
                const next = await call<SessionOut>("/demo/reset", { method: "POST" });
                adopt(next);
                setResult(null);
                setTampered(null);
              })
            }
          />
          <div className="mt-3 empty:hidden" aria-live="polite">
            <VerifyResult result={result} tampered={tampered} />
            {actionError && (
              <p role="alert" className="text-alarm text-sm">
                {actionError}
              </p>
            )}
          </div>
        </>
      )}
    />
  );
}
