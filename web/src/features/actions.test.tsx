import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RoleSwitcher } from "./role/RoleSwitcher";
import { TryItPanel } from "./actions/TryItPanel";
import { VerifyResult } from "./verify/VerifyResult";

const handlers = () => ({
  onAddVersion: vi.fn(),
  onTamperFile: vi.fn(),
  onTamperLog: vi.fn(),
  onReset: vi.fn(),
});

describe("RoleSwitcher", () => {
  it("shows the current role and switches", async () => {
    const onChange = vi.fn();
    render(<RoleSwitcher role="admin" onChange={onChange} busy={false} />);
    expect(screen.getByRole("radio", { name: "Admin" })).toBeChecked();
    await userEvent.click(screen.getByRole("radio", { name: "Auditor" }));
    expect(onChange).toHaveBeenCalledWith("auditor");
  });
});

describe("TryItPanel", () => {
  it("shows tamper buttons only to admins", () => {
    const { rerender } = render(<TryItPanel role="admin" pending={null} hasRecord {...handlers()} />);
    expect(screen.getByRole("button", { name: "Tamper with the log" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tamper with a file" })).toBeInTheDocument();
    rerender(<TryItPanel role="clinician" pending={null} hasRecord {...handlers()} />);
    expect(screen.queryByRole("button", { name: "Tamper with the log" })).not.toBeInTheDocument();
    expect(screen.getByText(/Switch to admin to tamper/)).toBeInTheDocument();
  });

  it("keeps tamper buttons in action ink; red is only for what broke", () => {
    render(<TryItPanel role="admin" pending={null} hasRecord {...handlers()} />);
    expect(screen.getByRole("button", { name: "Tamper with the log" })).not.toHaveClass("btn-alarm");
  });

  it("hides Add a version from auditors", () => {
    render(<TryItPanel role="auditor" pending={null} hasRecord {...handlers()} />);
    expect(screen.queryByRole("button", { name: "Add a version" })).not.toBeInTheDocument();
  });

  it("disables every action while one is pending", () => {
    render(<TryItPanel role="admin" pending="add" hasRecord {...handlers()} />);
    for (const name of ["Adding…", "Tamper with a file", "Tamper with the log", "Reset the demo"]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
  });

  it("calls the matching handler", async () => {
    const h = handlers();
    render(<TryItPanel role="admin" pending={null} hasRecord {...h} />);
    await userEvent.click(screen.getByRole("button", { name: "Tamper with the log" }));
    await userEvent.click(screen.getByRole("button", { name: "Reset the demo" }));
    expect(h.onTamperLog).toHaveBeenCalledOnce();
    expect(h.onReset).toHaveBeenCalledOnce();
  });
});

describe("VerifyResult", () => {
  it("prompts to verify after tampering", () => {
    render(<VerifyResult result={null} tampered="log" />);
    expect(screen.getByText(/Run Verify the chain to see whether it is caught/)).toBeInTheDocument();
  });

  it("reports an intact chain with counts", () => {
    render(
      <VerifyResult
        result={{ ok: true, checked_events: 350, checked_blobs: 341, first_broken_seq: null, reason: null }}
        tampered={null}
      />,
    );
    expect(screen.getByText("Chain intact: 350 entries and 341 files checked.")).toBeInTheDocument();
  });

  it("names the entry that does not reconcile", () => {
    render(
      <VerifyResult
        result={{ ok: false, checked_events: 175, checked_blobs: 0, first_broken_seq: 175, reason: "hash_mismatch" }}
        tampered="log"
      />,
    );
    expect(screen.getByText(/Broken at entry #175/)).toBeInTheDocument();
    expect(screen.getByText(/hash mismatch/)).toBeInTheDocument();
  });

  it("explains a changed file", () => {
    render(
      <VerifyResult
        result={{ ok: false, checked_events: 351, checked_blobs: 12, first_broken_seq: null, reason: "blob_mismatch" }}
        tampered="file"
      />,
    );
    expect(screen.getByText(/A stored file no longer matches its hash/)).toBeInTheDocument();
  });
});
