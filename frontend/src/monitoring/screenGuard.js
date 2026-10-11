// Fullscreen and extra displays. Fullscreen keeps notes and other windows off the interview screen; leaving it is
// recorded with its duration. A second connected display is noted once (Chromium browsers expose
// screen.isExtended; elsewhere it simply can't be checked). Neither says what was on the other screen, and both can
// have innocent causes (a notification, a docked laptop), so they are signals for a reviewer only.

export const FULLSCREEN_MIN_MS = 1000; // a sub-second flicker (permission prompt, OS animation) is not recorded

/** Pure episode tracker, like FocusTracker: returns an event when fullscreen is re-entered or the session ends. */
export class FullscreenTracker {
  constructor() { this.exitedAt = null; }

  exit(tMs) { if (this.exitedAt === null) this.exitedAt = tMs; }

  enter(tMs) {
    if (this.exitedAt === null) return null;
    const ev = { event_type: "fullscreen_exit", t_ms: Math.round(this.exitedAt),
      duration_ms: Math.round(tMs - this.exitedAt) };
    this.exitedAt = null;
    return ev.duration_ms >= FULLSCREEN_MIN_MS ? ev : null;
  }
}

/** Event for "a second display is connected", or null. `screenLike` is window.screen (injectable for tests). */
export function secondDisplayEvent(screenLike, tMs) {
  return screenLike && screenLike.isExtended === true
    ? { event_type: "second_display", t_ms: Math.max(0, Math.round(tMs)) } : null;
}

export class ScreenGuard {
  /** now(): interview-relative ms; onEvent(event); onWarning({type, message} | {clear: type}). */
  constructor({ now, onEvent, onWarning, doc = document, scr = window.screen }) {
    this.now = now;
    this.onEvent = onEvent;
    this.onWarning = onWarning;
    this.doc = doc;
    this.scr = scr;
    this.fs = new FullscreenTracker();
    this.reportedDisplay = false;
    this.active = false;
    this._fsChange = () => {
      if (!this.active) return;
      if (this.doc.fullscreenElement) {
        this.onEvent?.(this.fs.enter(this.now()));
        this.onWarning?.({ clear: "fullscreen_exit" });
      } else {
        this.fs.exit(this.now());
        this.onWarning?.({ type: "fullscreen_exit", message: "You left full screen. Please return to full screen to continue the interview." });
      }
    };
    this._screenChange = () => this._checkDisplays();
  }

  _checkDisplays() {
    if (this.reportedDisplay) return;
    const ev = secondDisplayEvent(this.scr, this.now());
    if (ev) {
      this.reportedDisplay = true;
      this.onEvent?.(ev);
      this.onWarning?.({ type: "second_display", message: "A second display seems to be connected. Please use a single screen during the interview." });
    }
  }

  /** Must be called from a user gesture (e.g. the Start button) so the browser allows fullscreen. */
  async start(element = this.doc.documentElement) {
    this.active = true;
    this.doc.addEventListener("fullscreenchange", this._fsChange);
    this.scr?.addEventListener?.("change", this._screenChange);
    this._checkDisplays();
    try {
      if (!this.doc.fullscreenElement) await element.requestFullscreen?.();
      return true;
    } catch {
      return false; // refused or unsupported: the interview still works, nothing is recorded for it
    }
  }

  /** Ask for fullscreen again (from a button in the warning). */
  async reenter(element = this.doc.documentElement) {
    try { await element.requestFullscreen?.(); return true; } catch { return false; }
  }

  async stop() {
    this.active = false;
    this.doc.removeEventListener("fullscreenchange", this._fsChange);
    this.scr?.removeEventListener?.("change", this._screenChange);
    this.onEvent?.(this.fs.enter(this.now())); // close an open episode
    if (this.doc.fullscreenElement) {
      try { await this.doc.exitFullscreen(); } catch { /* already left */ }
    }
  }
}
