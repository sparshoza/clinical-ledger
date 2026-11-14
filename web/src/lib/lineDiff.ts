export type DiffLine = { text: string; changed: boolean };

/**
 * Line-level comparison of two texts by longest common subsequence: lines outside the
 * common subsequence are marked changed on their own side. Documents here are a few
 * hundred lines at most, so the quadratic table is fine.
 */
export function lineDiff(beforeText: string, afterText: string): { before: DiffLine[]; after: DiffLine[] } {
  const a = beforeText.split("\n");
  const b = afterText.split("\n");
  const lcs: number[][] = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      lcs[i]![j] = a[i] === b[j] ? lcs[i + 1]![j + 1]! + 1 : Math.max(lcs[i + 1]![j]!, lcs[i]![j + 1]!);
    }
  }
  const keepA = new Array<boolean>(a.length).fill(false);
  const keepB = new Array<boolean>(b.length).fill(false);
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      keepA[i++] = true;
      keepB[j++] = true;
    } else if (lcs[i + 1]![j]! >= lcs[i]![j + 1]!) {
      i++;
    } else {
      j++;
    }
  }
  return {
    before: a.map((text, n) => ({ text, changed: !keepA[n] })),
    after: b.map((text, n) => ({ text, changed: !keepB[n] })),
  };
}
