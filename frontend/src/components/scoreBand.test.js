import { describe, expect, it } from "vitest";
import { scoreBand } from "./scoreBand";

describe("scoreBand", () => {
  it("maps scores to the same bands as the backend", () => {
    expect(scoreBand(100).text).toBe("Outstanding (90-100)");
    expect(scoreBand(89.9).text).toBe("Strong (75-89)");
    expect(scoreBand(75).key).toBe("strong");
    expect(scoreBand(60).key).toBe("competent");
    expect(scoreBand(59).text).toBe("Developing (40-59)");
    expect(scoreBand(0).text).toBe("Needs work (0-39)");
  });
  it("handles missing or out-of-range scores", () => {
    expect(scoreBand(null)).toBeNull();
    expect(scoreBand(undefined)).toBeNull();
    expect(scoreBand(140).key).toBe("outstanding");
    expect(scoreBand(-5).key).toBe("needs_work");
  });
});
