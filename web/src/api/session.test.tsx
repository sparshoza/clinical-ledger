import { act, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionProvider, useSession } from "./session";

const future = new Date(Date.now() + 3_600_000).toISOString();
const past = new Date(Date.now() - 3_600_000).toISOString();

function session(token: string, expires_at = future) {
  return { token, tenant_id: `t-${token}`, role: "admin", expires_at };
}

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

let api: ReturnType<typeof useSession> | null = null;
function Probe() {
  api = useSession();
  return null;
}

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
  api = null;
});

describe("SessionProvider", () => {
  it("renews an expired session once, however many requests hit the 401 together", async () => {
    localStorage.setItem("cl.session", JSON.stringify(session("old")));
    const signIns: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
      const auth = new Headers(init.headers).get("Authorization");
      if (url.endsWith("/auth/demo")) {
        signIns.push(auth ?? "none");
        return json(200, session("new"));
      }
      return auth === "Bearer new" ? json(200, { ok: true }) : json(401, { status: 401, title: "expired" });
    }));
    render(<SessionProvider><Probe /></SessionProvider>);
    await act(async () => {
      await Promise.all([api!.call("/stats"), api!.call("/records"), api!.call("/events")]);
    });
    expect(signIns).toHaveLength(1);
  });

  it("does not reuse a stored session that has already expired", async () => {
    localStorage.setItem("cl.session", JSON.stringify(session("stale", past)));
    const sent: (string | null)[] = [];
    vi.stubGlobal("fetch", vi.fn(async (_url: string, init: RequestInit) => {
      sent.push(new Headers(init.headers).get("Authorization"));
      return json(200, session("fresh"));
    }));
    render(<SessionProvider><Probe /></SessionProvider>);
    await waitFor(() => expect(api?.session?.token).toBe("fresh"));
    expect(sent[0]).toBeNull();
  });
});
