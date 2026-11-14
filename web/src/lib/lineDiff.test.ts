import { describe, expect, it } from "vitest";
import { lineDiff } from "./lineDiff";

describe("lineDiff", () => {
  it("marks nothing when the documents match", () => {
    const { before, after } = lineDiff("a\nb", "a\nb");
    expect(before.every((l) => !l.changed)).toBe(true);
    expect(after.every((l) => !l.changed)).toBe(true);
  });

  it("marks a replaced line on both sides and keeps the rest", () => {
    const { before, after } = lineDiff("a\nb\nc", "a\nB\nc");
    expect(before.map((l) => l.changed)).toEqual([false, true, false]);
    expect(after.map((l) => l.changed)).toEqual([false, true, false]);
  });

  it("marks added lines only on the after side", () => {
    const { before, after } = lineDiff("a\nc", "a\nb\nc");
    expect(before.map((l) => l.changed)).toEqual([false, false]);
    expect(after.map((l) => [l.text, l.changed])).toEqual([["a", false], ["b", true], ["c", false]]);
  });
});
