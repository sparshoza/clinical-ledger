import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { EventOut, StatsOut } from "../../api/types";
import { Landing } from "./Landing";
import { LivePreview } from "./LivePreview";
import { routeFor } from "../../lib/route";

const HASH = "9f3c" + "0".repeat(58) + "a1";
const stats: StatsOut = {
  events: 350, records: 75, versions: 350, head_seq: 350, head_hash: HASH,
  last_checkpoint_seq: null, last_verify: null, tenant_expires_at: "2026-11-16T12:00:00Z",
};
const events: EventOut[] = [
  { seq: 350, event_type: "version.added", record_id: "r1", version_no: 6, actor: "a1", actor_role: "clinician", occurred_at: "2026-11-14T11:00:00Z", payload: {}, prev_hash: "b".repeat(64), event_hash: HASH },
];

describe("Landing", () => {
  it("says what the project is, that the data is synthetic, and leads into the demo", () => {
    render(<Landing preview={<p>preview</p>} />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.getAllByText(/synthetic/i).length).toBeGreaterThan(0);
    const cta = screen.getAllByRole("link", { name: "Open the demo" })[0]!;
    expect(cta).toHaveAttribute("href", "/demo");
    expect(screen.getByRole("link", { name: "Source on GitHub" })).toHaveAttribute(
      "href", "https://github.com/sparshoza/clinical-ledger",
    );
    expect(screen.getByText("preview")).toBeInTheDocument();
  });

  it("explains the mechanisms and shows measured numbers with a link to the method", () => {
    render(<Landing preview={null} />);
    expect(screen.getByRole("heading", { name: "How it works" })).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Measured on a laptop" });
    expect(within(table).getByText("1.36 ms")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /method and hardware/i })).toBeInTheDocument();
  });
});

describe("LivePreview", () => {
  it("shows the visitor's own ledger and verifies it on request", async () => {
    const onVerify = vi.fn();
    render(<LivePreview stats={stats} events={events} onVerify={onVerify} verifying={false} result={null} />);
    expect(screen.getByText(/350 entries/)).toBeInTheDocument();
    expect(screen.getByText("Version added")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Verify the chain" }));
    expect(onVerify).toHaveBeenCalledOnce();
  });

  it("reports an intact chain in words", () => {
    render(
      <LivePreview stats={stats} events={events} onVerify={() => {}} verifying={false}
        result={{ ok: true, checked_events: 350, checked_blobs: 350, first_broken_seq: null, reason: null }} />,
    );
    expect(screen.getByText(/Chain intact/)).toBeInTheDocument();
  });

  it("waits calmly while the ledger is being created", () => {
    render(<LivePreview stats={null} events={[]} onVerify={() => {}} verifying={false} result={null} />);
    expect(screen.getByText(/Creating your private ledger/)).toBeInTheDocument();
  });
});

describe("LivePreview when the ledger cannot be created", () => {
  it("says why instead of waiting forever", () => {
    render(
      <LivePreview stats={null} events={[]} onVerify={() => {}} verifying={false} result={null}
        error={{ title: "Too many new demo ledgers", detail: "Try again later." }} />,
    );
    expect(screen.getByText("Too many new demo ledgers")).toBeInTheDocument();
    expect(screen.queryByText(/Creating your private ledger/)).not.toBeInTheDocument();
  });
});

describe("routeFor", () => {
  it("sends /demo and its sub-paths to the console and everything else to the landing page", () => {
    expect(routeFor("/demo")).toBe("demo");
    expect(routeFor("/demo/")).toBe("demo");
    expect(routeFor("/")).toBe("landing");
    expect(routeFor("/about")).toBe("landing");
  });
});
