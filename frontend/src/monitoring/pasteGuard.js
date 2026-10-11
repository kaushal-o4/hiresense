// Notices text pasted into an answer box (typed interview answers, coding questions). Only the fact that a paste
// happened is recorded, never the pasted text. Short pastes (a variable name, a fixed typo) are ignored.
// Like every integrity signal this is for a human reviewer: pasting your own notes can be legitimate.

export const PASTE_MIN_CHARS = 40;

/** Event for one paste, or null if it is too short to matter. */
export function pasteEvent(text, tMs, minChars = PASTE_MIN_CHARS) {
  const n = (text || "").trim().length;
  if (n < minChars) return null;
  return { event_type: "paste_detected", t_ms: Math.max(0, Math.round(tMs)) };
}

const isAnswerField = (el) => !!el && (el.tagName === "TEXTAREA" || el.isContentEditable
  || (el.tagName === "INPUT" && /^(text|search)?$/i.test(el.type || "")));

export class PasteGuard {
  /** now(): interview-relative ms; onEvent(event); onWarning({type, message}) shown to the candidate. */
  constructor({ now, onEvent, onWarning, minChars = PASTE_MIN_CHARS }) {
    this.now = now;
    this.onEvent = onEvent;
    this.onWarning = onWarning;
    this.minChars = minChars;
    this._paste = (e) => {
      if (!isAnswerField(e.target)) return;
      const ev = pasteEvent(e.clipboardData?.getData("text") || "", this.now(), this.minChars);
      if (!ev) return;
      this.onEvent?.(ev);
      this.onWarning?.({ type: "paste_detected",
        message: "Pasted text was noticed in your answer. Please answer in your own words." });
    };
  }

  attach(root = document) {
    this.root = root;
    root.addEventListener("paste", this._paste, true);
  }

  detach() {
    this.root?.removeEventListener("paste", this._paste, true);
    this.root = null;
  }
}
