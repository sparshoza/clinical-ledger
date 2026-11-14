import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, apiFetch } from "./client";
import type { Role, SessionOut } from "./types";

const STORAGE_KEY = "cl.session";
const DEFAULT_ROLE: Role = "admin";

type Session = {
  session: SessionOut | null;
  error: ApiError | null;
  /** Switch role, keeping this visitor's private ledger. */
  signIn: (role: Role) => Promise<void>;
  /** Replace the session (after a reset). */
  adopt: (next: SessionOut) => void;
  /** Call the API as the current visitor; re-signs once if the demo session expired. */
  call: <T>(path: string, init?: { method?: string; body?: unknown }) => Promise<T>;
  retry: () => void;
};

const SessionContext = createContext<Session | null>(null);

function load(): SessionOut | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as SessionOut) : null;
  } catch {
    return null;
  }
}

function save(session: SessionOut | null) {
  try {
    if (session) localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable: the session lives in memory only */
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionOut | null>(load);
  const [error, setError] = useState<ApiError | null>(null);
  const [attempt, setAttempt] = useState(0);
  const current = useRef(session);
  current.current = session;

  const adopt = useCallback((next: SessionOut) => {
    save(next);
    current.current = next;
    setSession(next);
    setError(null);
  }, []);

  const signIn = useCallback(
    async (role: Role) => {
      const next = await apiFetch<SessionOut>("/auth/demo", {
        method: "POST",
        token: current.current?.token,
        body: { role },
      });
      adopt(next);
    },
    [adopt],
  );

  useEffect(() => {
    if (session) return;
    signIn(DEFAULT_ROLE).catch((err: unknown) => {
      setError(err instanceof ApiError ? err : new ApiError({ status: 503, title: "Sign-in failed" }));
    });
  }, [session, signIn, attempt]);

  const call = useCallback(
    async <T,>(path: string, init: { method?: string; body?: unknown } = {}) => {
      try {
        return await apiFetch<T>(path, { ...init, token: current.current?.token });
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          await signIn(current.current?.role ?? DEFAULT_ROLE);
          return apiFetch<T>(path, { ...init, token: current.current?.token });
        }
        throw err;
      }
    },
    [signIn],
  );

  const value = useMemo<Session>(
    () => ({
      session,
      error,
      signIn,
      adopt,
      call,
      retry: () => {
        setError(null);
        setAttempt((n) => n + 1);
      },
    }),
    [session, error, signIn, adopt, call],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
