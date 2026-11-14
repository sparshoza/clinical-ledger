import { describe, expect, it } from "vitest";
import { formatDate, formatRelative, patientLabel, shortHash } from "./format";

describe("shortHash", () => {
  it("keeps the first four and last two characters", () => {
    expect(shortHash("9f3c" + "0".repeat(58) + "a1")).toBe("9f3c…a1");
  });
  it("returns short values unchanged", () => {
    expect(shortHash("abc")).toBe("abc");
  });
});

describe("formatRelative", () => {
  const now = new Date("2026-11-14T12:00:00Z");
  it.each([
    ["2026-11-14T11:59:40Z", "just now"],
    ["2026-11-14T11:58:00Z", "2 min ago"],
    ["2026-11-14T09:00:00Z", "3 h ago"],
    ["2026-11-10T12:00:00Z", "4 days ago"],
    ["2026-11-13T12:00:00Z", "1 day ago"],
  ])("%s is %s", (iso, expected) => {
    expect(formatRelative(iso, now)).toBe(expected);
  });
});

describe("formatDate", () => {
  it("uses day month year without commas", () => {
    expect(formatDate("2026-11-06T10:00:00Z")).toBe("6 Nov 2026");
  });
});

describe("patientLabel", () => {
  it("shortens a FHIR patient reference", () => {
    expect(patientLabel("Patient/068177c1-8d2f-d13f-6a1d-227d04383923")).toBe("Patient 068177c1");
  });
  it("leaves other references alone", () => {
    expect(patientLabel("Device/x")).toBe("Device/x");
  });
});
