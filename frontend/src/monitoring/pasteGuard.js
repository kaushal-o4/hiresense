// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/monitoring/pasteGuard.js
//
// FILE PURPOSE:
// Notices when text is pasted into an answer box, without recording the pasted text.
//
// WHAT THIS FILE DOES:
// 1. Ignores short pastes (under 40 characters).
// 2. Records 'paste_detected' or, from 200 characters, 'paste_long'.
// 3. Warns the candidate only for long pastes.
//
// HOW THIS FILE WORKS:
// PasteGuard.attach() listens for paste events on answer fields; pasteEvent() builds the event.
//
// IMPORTANT FUNCTIONS:
//    - PasteGuard()
//        Attaches/detaches the paste listener.
//    - pasteEvent()
//        Creates an event for one paste or returns null.
//    - isAnswerField()
//        Checks whether the paste happened in an answer field.
//
// INPUT:
// Browser paste events.
//
// OUTPUT:
// Paste events for the reporter.
//
// FILES CONNECTED TO THIS FILE:
//    Used by: monitoring/interviewMonitor.js
//    Tested by: monitoring/browserGuards.test.js
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
// Notices text pasted into an answer box (typed interview answers, coding questions). Only the fact that a paste
// happened, and whether it was long, is recorded - never the pasted text. Short pastes (a variable name, a fixed
// typo) are ignored. Pasting is also a legitimate input route (dictation and accessibility tools), so a normal
// paste is informational and only long pastes stand out for a human reviewer.

export const PASTE_MIN_CHARS = 40;
export const PASTE_LONG_CHARS = 200; // roughly a full paragraph-length answer

/** Event for one paste ("paste_detected" or, from PASTE_LONG_CHARS, "paste_long"), or null if too short. */
export function pasteEvent(text, tMs, minChars = PASTE_MIN_CHARS) {
  const n = (text || "").trim().length;
  if (n < minChars) return null;
  return { event_type: n >= PASTE_LONG_CHARS ? "paste_long" : "paste_detected", t_ms: Math.max(0, Math.round(tMs)) };
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
      if (ev.event_type === "paste_long") { // a short paste isn't worth interrupting the candidate for
        this.onWarning?.({ type: "paste_long",
          message: "A long pasted text was noticed in your answer. Please answer in your own words." });
      }
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
