// Ordering logic for streamed speech, kept free of audio APIs so it can be unit-tested.
//
// Speech arrives as numbered sentences in "lanes" that play one after another (e.g. "greeting" then
// "question"). A sentence's text is known first; its audio arrives later (or it falls back to the browser voice).
// Playback never skips ahead: sentence n+1 waits for sentence n, and a lane starts only after the previous lane is
// closed and finished. This is what keeps audio ordered and non-overlapping.

export class SpeechQueue {
  constructor(laneNames) {
    this.lanes = laneNames.map((name) => ({ name, slots: [], closed: false, browserFrom: Infinity }));
    this.lane = 0; // lane being played
    this.slot = 0; // next slot to play in that lane
    this.played = []; // slots handed out for playback, in order (for subtitles)
  }

  _lane(name) {
    const l = this.lanes.find((x) => x.name === name);
    if (!l) throw new Error(`unknown lane ${name}`);
    return l;
  }

  /** Text of sentence `index` in `lane` is known (audio may follow). */
  add(lane, index, text) {
    const l = this._lane(lane);
    const slot = l.slots[index] || { text: "", payload: null };
    slot.text = text;
    if (index >= l.browserFrom && !slot.payload) slot.payload = { kind: "browser" };
    l.slots[index] = slot;
  }

  /** Audio for a sentence: {kind: "phoneme", res} or {kind: "browser"}. */
  fill(lane, index, payload) {
    const l = this._lane(lane);
    const slot = l.slots[index] || { text: payload?.res?.text || "", payload: null };
    slot.payload = payload;
    l.slots[index] = slot;
  }

  /** Local voice failed: sentences from `index` on (and later ones) use the browser voice. */
  browserFrom(lane, index) {
    const l = this._lane(lane);
    l.browserFrom = Math.min(l.browserFrom, index);
    l.slots.forEach((s, i) => { if (s && i >= index && !s.payload) s.payload = { kind: "browser" }; });
  }

  close(lane) {
    this._lane(lane).closed = true;
  }

  /** Drop everything not yet played in `lane` (a retracted reply). Returns true if that lane is playing now. */
  retract(lane) {
    const li = this.lanes.findIndex((x) => x.name === lane);
    const l = this.lanes[li];
    const playingNow = li === this.lane && this.slot > 0;
    l.slots = [];
    l.closed = false;
    l.browserFrom = Infinity;
    if (li === this.lane) this.slot = 0;
    this.played = this.played.filter((p) => p.lane !== lane);
    return playingNow;
  }

  /** What to do next: {state: "play", slot, lane, index} | {state: "wait"} | {state: "done"}. */
  next() {
    while (this.lane < this.lanes.length) {
      const l = this.lanes[this.lane];
      const s = l.slots[this.slot];
      if (s && s.payload) {
        const out = { state: "play", slot: s, lane: l.name, index: this.slot };
        this.played.push({ lane: l.name, index: this.slot, text: s.text });
        this.slot += 1;
        return out;
      }
      if (s || !l.closed) return { state: "wait" };
      this.lane += 1; // lane finished
      this.slot = 0;
    }
    return { state: "done" };
  }

  /** All sentence texts known so far, in speaking order (subtitles show what is/will be said). */
  fullText() {
    return this.lanes.flatMap((l) => l.slots.filter(Boolean).map((s) => s.text)).filter(Boolean).join(" ");
  }

  /** Character offset (in fullText) where the sentence currently playing starts, and its length. */
  currentSpan() {
    const last = this.played[this.played.length - 1];
    if (!last) return { start: 0, length: 0 };
    let start = 0;
    for (const l of this.lanes) {
      for (let i = 0; i < l.slots.length; i++) {
        const s = l.slots[i];
        if (!s?.text) continue;
        if (l.name === last.lane && i === last.index) return { start, length: s.text.length };
        start += s.text.length + 1;
      }
    }
    return { start: 0, length: 0 };
  }
}
