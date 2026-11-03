import { describe, expect, it } from "vitest";
import { vadStep } from "./recorder";
import { SpeechQueue } from "./speechQueue";
import { createSseParser } from "./turnStream";

const res = (t) => ({ kind: "phoneme", res: { text: t } });

describe("SpeechQueue (ordered, non-overlapping streamed speech)", () => {
  it("never skips ahead: sentence 2 waits for sentence 1's audio", () => {
    const q = new SpeechQueue(["intro", "question"]);
    q.close("intro");
    q.add("question", 0, "First.");
    q.add("question", 1, "Second.");
    q.fill("question", 1, res("Second."));
    expect(q.next().state).toBe("wait");
    q.fill("question", 0, res("First."));
    expect(q.next().slot.text).toBe("First.");
    expect(q.next().slot.text).toBe("Second.");
    expect(q.next().state).toBe("wait"); // lane still open
    q.close("question");
    expect(q.next().state).toBe("done");
  });

  it("plays the greeting lane before the question lane", () => {
    const q = new SpeechQueue(["intro", "question"]);
    q.add("question", 0, "Question?");
    q.fill("question", 0, res("Question?"));
    q.add("intro", 0, "Hello, I'm Aria.");
    expect(q.next().state).toBe("wait"); // intro not ready yet - question must not jump ahead
    q.fill("intro", 0, res("Hello"));
    q.close("intro");
    expect(q.next().lane).toBe("intro");
    expect(q.next().lane).toBe("question");
  });

  it("falls back to the browser voice from a failed sentence on", () => {
    const q = new SpeechQueue(["question"]);
    q.add("question", 0, "A b c.");
    q.fill("question", 0, res("A b c."));
    q.browserFrom("question", 1);
    q.add("question", 1, "D e f.");
    q.next();
    expect(q.next().slot.payload.kind).toBe("browser");
  });

  it("retract drops unplayed sentences; subtitles track the playing sentence", () => {
    const q = new SpeechQueue(["question"]);
    q.add("question", 0, "Old one.");
    q.fill("question", 0, res("x"));
    q.next();
    expect(q.retract("question")).toBe(true);
    q.add("question", 0, "New question here.");
    q.add("question", 1, "Second part.");
    q.fill("question", 0, res("y"));
    q.next();
    expect(q.fullText()).toBe("New question here. Second part.");
    expect(q.currentSpan()).toEqual({ start: 0, length: 18 });
  });
});

describe("SSE parser", () => {
  it("handles events split across chunks and keep-alive comments", () => {
    const p = createSseParser();
    expect(p("event: sentence\ndata: {\"index\": 0, \"te")).toEqual([]);
    expect(p("xt\": \"Hi.\"}\n\n: keep-alive\n\nevent: done\ndata: {}\n\n")).toEqual([
      { event: "sentence", data: { index: 0, text: "Hi." } }, { event: "done", data: {} }]);
  });
});

describe("end-of-speech detection", () => {
  const feed = (opts, pattern) => {
    const st = { elapsed: 0, speechMs: 0, quietMs: 0, started: false, warned: false };
    let out = null;
    for (const [level, ms] of pattern) {
      for (let t = 0; t < ms && !out; t += 20) {
        const r = vadStep(st, level, 20, opts);
        if (r === "silence_stop") out = st.elapsed;
      }
    }
    return out;
  };

  it("ends the answer after the configured pause", () => {
    expect(feed({ silenceMs: 1000 }, [[0.1, 3000], [0, 2000]])).toBeCloseTo(4000, -2);
  });

  it("a pause right after a few words does not end the answer (minimum speech)", () => {
    expect(feed({ silenceMs: 1000, minAnswerMs: 1200 }, [[0.1, 500], [0, 1500]])).toBeNull();
    expect(feed({ silenceMs: 1000, minAnswerMs: 1200 }, [[0.1, 500], [0, 1500], [0.1, 1000], [0, 1200]])).not.toBeNull();
  });
});
