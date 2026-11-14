import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AuditLog } from "./audit/AuditLog";
import { ContentPanel } from "./timeline/ContentPanel";
import { ErrorState } from "./status/ErrorState";
import { RecordList } from "./records/RecordList";
import { StatusBar } from "./status/StatusBar";
import { Timeline } from "./timeline/Timeline";
import { VersionCompare } from "./timeline/VersionCompare";
import type { EventOut, RecordSummaryOut, StatsOut, VersionOut } from "../api/types";

const HASH = "9f3c" + "0".repeat(58) + "a1";

const stats: StatsOut = {
  events: 350,
  records: 75,
  versions: 350,
  head_seq: 350,
  head_hash: HASH,
  last_checkpoint_seq: null,
  last_verify: null,
  tenant_expires_at: "2026-11-15T12:00:00Z",
};

const records: RecordSummaryOut[] = [
  { id: "r1", kind: "patient-summary", subject_ref: "Patient/aaaaaaaa-1", latest_version_no: 4, updated_at: "2026-11-01T00:00:00Z" },
  { id: "r2", kind: "lab-panel", subject_ref: "Patient/aaaaaaaa-1", latest_version_no: 3, updated_at: "2026-11-02T00:00:00Z" },
  { id: "r3", kind: "imaging-report", subject_ref: "Patient/bbbbbbbb-2", latest_version_no: 3, updated_at: "2026-11-03T00:00:00Z" },
];

const versions: VersionOut[] = [1, 2, 3].map((n) => ({
  record_id: "r1",
  version_no: n,
  content_hash: HASH,
  created_at: `2026-1${n}-01T00:00:00Z`.replace("2026-13", "2026-12"),
  note: n === 1 ? "Initial record" : `Added condition ${n}`,
}));

const events: EventOut[] = [
  { seq: 12, event_type: "record.read", record_id: "r1", version_no: 3, actor: "a1", actor_role: "clinician", occurred_at: "2026-11-14T11:00:00Z", payload: {}, prev_hash: "b".repeat(64), event_hash: HASH },
  { seq: 11, event_type: "version.added", record_id: "r1", version_no: 3, actor: "a1", actor_role: "clinician", occurred_at: "2026-11-14T10:00:00Z", payload: {}, prev_hash: "c".repeat(64), event_hash: "b".repeat(64) },
];

describe("StatusBar", () => {
  it("shows the chain head, entry count and synthetic data notice", () => {
    render(<StatusBar stats={stats} onVerify={() => {}} canVerify verifying={false} />);
    expect(screen.getByText("9f3c…a1")).toBeInTheDocument();
    expect(screen.getByText(/350 entries/)).toBeInTheDocument();
    expect(screen.getByText(/Not verified yet/)).toBeInTheDocument();
  });

  it("disables Verify for roles that cannot verify, and says why", () => {
    render(<StatusBar stats={stats} onVerify={() => {}} canVerify={false} verifying={false} />);
    expect(screen.getByRole("button", { name: "Verify the chain" })).toBeDisabled();
    expect(screen.getByText(/Switch to auditor or admin to verify/)).toBeInTheDocument();
  });

  it("calls onVerify", async () => {
    const onVerify = vi.fn();
    render(<StatusBar stats={stats} onVerify={onVerify} canVerify verifying={false} />);
    await userEvent.click(screen.getByRole("button", { name: "Verify the chain" }));
    expect(onVerify).toHaveBeenCalledOnce();
  });
});

describe("RecordList", () => {
  it("groups records by patient and marks the selection", async () => {
    const onSelect = vi.fn();
    render(<RecordList records={records} selectedId="r2" onSelect={onSelect} />);
    expect(screen.getByText("Patient aaaaaaaa")).toBeInTheDocument();
    expect(screen.getByText("Patient bbbbbbbb")).toBeInTheDocument();
    const selected = screen.getByRole("button", { name: /Lab panel/ });
    expect(selected).toHaveAttribute("aria-current", "true");
    await userEvent.click(screen.getByRole("button", { name: /Imaging report/ }));
    expect(onSelect).toHaveBeenCalledWith("r3");
  });
});

describe("Timeline", () => {
  it("lists versions with the latest marked and selects one", async () => {
    const onSelect = vi.fn();
    render(<Timeline versions={versions} selected={3} onSelect={onSelect} />);
    const rows = screen.getAllByRole("button", { name: /^Version \d/ });
    expect(rows).toHaveLength(3);
    expect(screen.getByRole("button", { name: /Version 3, latest/ })).toHaveAttribute("aria-current", "true");
    await userEvent.click(screen.getByRole("button", { name: /Version 1/ }));
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("moves the as-of slider to an earlier version", () => {
    const onSelect = vi.fn();
    render(<Timeline versions={versions} selected={3} onSelect={onSelect} />);
    const slider = screen.getByRole("slider", { name: "Show the record as of" });
    slider.focus();
    // keyboard: one step left selects version 2
    slider.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
    expect(slider).toHaveAttribute("aria-valuemax", "3");
  });
});

describe("ContentPanel", () => {
  it("shows formatted JSON for readers", () => {
    render(<ContentPanel role="clinician" content={{ status: "final" }} loading={false} error={null} />);
    expect(screen.getByText(/"status": "final"/)).toBeInTheDocument();
  });

  it("tells auditors they cannot see content", () => {
    render(<ContentPanel role="auditor" content={null} loading={false} error={null} />);
    expect(screen.getByText("Auditors can see the log but not record content.")).toBeInTheDocument();
  });

  it("keeps other read errors out of alarm red, which means a failed hash check", () => {
    render(<ContentPanel role="admin" content={null} loading={false} error={{ status: 404, title: "Version not found" }} />);
    expect(screen.getByRole("alert")).not.toHaveClass("text-alarm");
  });

  it("explains tampered content", () => {
    render(<ContentPanel role="admin" content={null} loading={false} error={{ status: 409, title: "Stored content does not match its hash" }} />);
    expect(screen.getByText(/does not match its hash/)).toBeInTheDocument();
  });
});

describe("AuditLog", () => {
  it("shows entry number, actor and role, event and carried hash", () => {
    render(<AuditLog events={events} brokenSeq={null} />);
    const table = screen.getByRole("table", { name: "Journal" });
    const first = within(table).getAllByRole("row")[1]!;
    expect(within(first).getByText("12")).toBeInTheDocument();
    expect(within(first).getByText("Record read")).toBeInTheDocument();
    expect(within(first).getByText("clinician")).toBeInTheDocument();
    expect(within(first).getByText("9f3c…a1")).toBeInTheDocument();
  });

  it("marks the entry that does not reconcile with text, not only colour", () => {
    render(<AuditLog events={events} brokenSeq={11} />);
    expect(screen.getByText("Does not reconcile")).toHaveClass("whitespace-nowrap");
  });

  it("shows the recomputed hash beside the stored one on the broken entry", () => {
    const computed = "7e01" + "0".repeat(58) + "ff";
    render(<AuditLog events={events} brokenSeq={11} mismatch={{ stored: "b".repeat(64), computed }} />);
    expect(screen.getByText("7e01…ff")).toBeInTheDocument();
    expect(screen.getByText(/Recomputed/)).toBeInTheDocument();
  });

  it("separates the entries written after the break", () => {
    render(<AuditLog events={events} brokenSeq={11} />);
    expect(screen.getByText(/after the break/)).toBeInTheDocument();
  });
});

describe("VersionCompare", () => {
  it("shows the previous and selected versions side by side and marks changed lines", () => {
    render(<VersionCompare previous={{ status: "draft", id: 1 }} current={{ status: "final", id: 1 }} previousNo={2} currentNo={3} />);
    expect(screen.getByRole("heading", { name: "Version 2" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Version 3" })).toBeInTheDocument();
    const changed = document.querySelectorAll("[data-changed]");
    expect(changed).toHaveLength(2);
    expect(changed[0]).toHaveTextContent('"status": "draft"');
    expect(changed[1]).toHaveTextContent('"status": "final"');
  });

  it("keeps wrapped lines indented under their key", () => {
    render(<VersionCompare previous={{ a: "x" }} current={{ a: "y" }} previousNo={1} currentNo={2} />);
    const text = document.querySelector('[data-changed="after"] [data-line]') as HTMLElement;
    expect(text.textContent).toBe('"a": "y"');
    expect(text.style.paddingLeft).toBe("4ch");
    expect(text.style.textIndent).toBe("-2ch");
  });
});

describe("RecordList on a phone", () => {
  it("offers to show every patient when the list is long", async () => {
    const many: RecordSummaryOut[] = Array.from({ length: 9 }, (_, i) => ({
      id: `m${i}`, kind: "lab-panel", subject_ref: `Patient/p${i}aaaaaa-1`, latest_version_no: 3, updated_at: "2026-11-01T00:00:00Z",
    }));
    render(<RecordList records={many} selectedId={null} onSelect={() => {}} />);
    const more = screen.getByRole("button", { name: "Show all 9 patients" });
    expect(more).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(more);
    expect(screen.queryByRole("button", { name: /Show all/ })).not.toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("names the problem and offers a retry", async () => {
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);
    expect(screen.getByText("The server is waking up or unreachable.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe("ErrorState with a reason", () => {
  it("shows the server's reason when it gave one", () => {
    render(<ErrorState onRetry={() => {}} reason={{ title: "Too many new demo ledgers", detail: "Try again later." }} />);
    expect(screen.getByText("Too many new demo ledgers")).toBeInTheDocument();
    expect(screen.getByText("Try again later.")).toBeInTheDocument();
  });
});

describe("StatusBar while busy", () => {
  it("disables Verify while another action is running", () => {
    render(<StatusBar stats={stats} onVerify={() => {}} canVerify verifying={false} busy />);
    expect(screen.getByRole("button", { name: "Verify the chain" })).toBeDisabled();
  });
});
