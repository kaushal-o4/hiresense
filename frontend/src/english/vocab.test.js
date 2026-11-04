import { describe, expect, it } from "vitest";
import {
  answer, boxLabel, currentCard, dueText, flip, isFinished, planSummary, reviewProgress, startReview, trendRows,
} from "./vocab";

const cards = [{ id: 1, front: "I go", back: "I went" }, { id: 2, front: "a apple", back: "an apple" }];

describe("review session", () => {
  it("walks through the cards and counts answers", () => {
    let s = startReview(cards);
    expect(currentCard(s).card.id).toBe(1);
    s = flip(s);
    expect(s.flipped).toBe(true);
    let r = answer(s, true);
    expect(r.send).toBe(true);
    s = r.state;
    expect(s.flipped).toBe(false);
    r = answer(s, true, { masteredNow: true });
    s = r.state;
    expect(isFinished(s)).toBe(true);
    expect([s.knew, s.notYet, s.mastered]).toEqual([2, 0, 1]);
  });

  it("shows a 'not yet' card once more at the end, without sending the repeat", () => {
    let s = startReview(cards);
    let r = answer(s, false);
    expect(r.send).toBe(true);
    s = answer(r.state, true).state;
    expect(isFinished(s)).toBe(false);
    expect(currentCard(s)).toEqual({ card: cards[0], repeat: true });
    expect(reviewProgress(s)).toEqual({ answered: 2, total: 2, repeatsLeft: 1 });
    r = answer(s, false);
    expect(r.send).toBe(false);
    expect(isFinished(r.state)).toBe(true); // a repeat is never queued again
    expect([r.state.knew, r.state.notYet]).toEqual([1, 1]);
  });

  it("ignores answers and flips after the end", () => {
    const s = startReview([]);
    expect(isFinished(s)).toBe(true);
    expect(answer(s, true)).toEqual({ state: s, send: false });
    expect(flip(s)).toBe(s);
  });
});

describe("formatting", () => {
  it("labels boxes", () => {
    expect(boxLabel(1)).toBe("New");
    expect(boxLabel(4)).toBe("Learned");
    expect(boxLabel(5, true)).toBe("Mastered");
    expect(boxLabel(undefined)).toBe("New");
  });

  it("describes when a card is due", () => {
    const now = new Date("2026-11-04T10:00:00Z");
    expect(dueText("2026-11-04T09:00:00Z", now)).toBe("Due now");
    expect(dueText("2026-11-05T09:00:00Z", now)).toBe("Due tomorrow");
    expect(dueText("2026-11-08T10:00:00Z", now)).toBe("Due in 4 days");
    expect(dueText(null, now)).toBe("");
  });

  it("summarises a plan", () => {
    expect(planSummary(null)).toEqual({ done: 0, total: 0, percent: 0, allDone: false });
    expect(planSummary({ items: [{ done: true }, { done: false }, { done: true }] }))
      .toEqual({ done: 2, total: 3, percent: 67, allDone: false });
    expect(planSummary({ items: [{ done: true }] }).allDone).toBe(true);
  });

  it("scales skill scores to 0-100 for the trend chart", () => {
    expect(trendRows([{ date: "2026-11-01", overall: 62.5, grammar: 6, vocabulary: 7, fluency: null, sentence_formation: 5.5 }]))
      .toEqual([{ date: "2026-11-01", overall: 62.5, grammar: 60, vocabulary: 70, fluency: null, sentence_formation: 55 }]);
    expect(trendRows([{ overall: 50 }])[0].date).toBe("#1");
  });
});
