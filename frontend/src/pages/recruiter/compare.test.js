import { describe, expect, it } from "vitest";
import { leaderIndex, parseIds } from "./CompareCandidates";

describe("compare helpers", () => {
  it("parses up to four distinct positive ids from the URL", () => {
    expect(parseIds("3,5,5,x,-1,8,9,10")).toEqual([3, 5, 8, 9]);
    expect(parseIds(null)).toEqual([]);
  });

  it("marks a single clear leader only", () => {
    expect(leaderIndex([70, 82, 60])).toBe(1);
    expect(leaderIndex([80, 80])).toBe(-1); // tie
    expect(leaderIndex([null, 50])).toBe(-1); // nothing to compare against
    expect(leaderIndex([null, 50, 40])).toBe(1);
  });
});
