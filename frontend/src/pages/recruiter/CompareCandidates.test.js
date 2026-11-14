// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/recruiter/CompareCandidates.test.js
//
// FILE PURPOSE:
// Unit tests for the helpers of CompareCandidates.jsx.
//
// WHAT THIS FILE DOES:
// 1. parseIds accepts up to four distinct positive ids.
// 2. leaderIndex marks only a single clear leader.
//
// HOW THIS FILE WORKS:
// Vitest tests.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: pages/recruiter/CompareCandidates.jsx
//
// IMPORTANT DEPENDENCIES:
//    vitest
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
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
