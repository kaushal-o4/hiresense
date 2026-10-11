import { describe, expect, it, vi } from "vitest";
import { ObjectTracker, observeObjects } from "./objectMonitor";
import { PASTE_LONG_CHARS, PASTE_MIN_CHARS, PasteGuard, pasteEvent } from "./pasteGuard";
import { FullscreenTracker, ScreenGuard, secondDisplayEvent } from "./screenGuard";

const det = (name, score) => ({ categories: [{ categoryName: name, score }] });

describe("paste detection", () => {
  it("ignores short pastes and never records the text", () => {
    expect(pasteEvent("myVar", 1000)).toBeNull();
    const ev = pasteEvent("x".repeat(PASTE_MIN_CHARS), 1234.6);
    expect(ev).toEqual({ event_type: "paste_detected", t_ms: 1235 });
    expect(JSON.stringify(ev)).not.toContain("xxx");
    expect(pasteEvent("y".repeat(PASTE_LONG_CHARS), 0).event_type).toBe("paste_long");
  });

  it("only watches answer fields, and only interrupts the candidate for long pastes", () => {
    const onEvent = vi.fn();
    const onWarning = vi.fn();
    const g = new PasteGuard({ now: () => 500, onEvent, onWarning });
    const paste = (tagName, text) => g._paste({ target: { tagName }, clipboardData: { getData: () => text } });
    paste("TEXTAREA", "a".repeat(80));
    paste("DIV", "a".repeat(80));
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onWarning).not.toHaveBeenCalled();
    paste("TEXTAREA", "b".repeat(300));
    expect(onWarning).toHaveBeenCalledWith(expect.objectContaining({ type: "paste_long" }));
  });
});

describe("fullscreen and displays", () => {
  it("records time outside fullscreen, ignoring sub-second flickers", () => {
    const f = new FullscreenTracker();
    f.exit(1000);
    expect(f.enter(1400)).toBeNull();
    f.exit(5000);
    f.exit(5500); // repeated exit keeps the first time
    expect(f.enter(9000)).toEqual({ event_type: "fullscreen_exit", t_ms: 5000, duration_ms: 4000 });
    expect(f.enter(9500)).toBeNull();
  });

  it("notes a second display only where the browser reports it", () => {
    expect(secondDisplayEvent({ isExtended: true }, 10)).toEqual({ event_type: "second_display", t_ms: 10 });
    expect(secondDisplayEvent({ isExtended: false }, 10)).toBeNull();
    expect(secondDisplayEvent({}, 10)).toBeNull(); // Firefox/Safari: unknown, never assumed
  });

  it("reports a second display once and closes an open fullscreen episode on stop", async () => {
    const events = [];
    const listeners = {};
    const doc = { fullscreenElement: null, documentElement: { requestFullscreen: vi.fn(async () => { doc.fullscreenElement = {}; }) },
      addEventListener: (n, f) => { listeners[n] = f; }, removeEventListener: vi.fn(), exitFullscreen: vi.fn() };
    let t = 0;
    const g = new ScreenGuard({ now: () => t, onEvent: (e) => e && events.push(e), doc,
      scr: { isExtended: true, addEventListener: vi.fn(), removeEventListener: vi.fn() } });
    await g.start();
    g._screenChange();
    expect(events.filter((e) => e.event_type === "second_display")).toHaveLength(1);
    t = 2000; doc.fullscreenElement = null; listeners.fullscreenchange();
    t = 7000;
    await g.stop();
    expect(events.at(-1)).toEqual({ event_type: "fullscreen_exit", t_ms: 2000, duration_ms: 5000 });
  });
});

describe("object detection", () => {
  it("counts only confident phones and books", () => {
    expect(observeObjects({ detections: [det("cell phone", 0.9), det("book", 0.4)] }))
      .toEqual({ phone_in_view: true, notes_in_view: false });
    expect(observeObjects({ detections: [det("cell phone", 0.2), det("laptop", 0.99)] }))
      .toEqual({ phone_in_view: false, notes_in_view: false });
    expect(observeObjects(null)).toEqual({ phone_in_view: false, notes_in_view: false });
  });

  it("needs a phone to persist before warning, and records it with confidence", () => {
    const tr = new ObjectTracker();
    const warnings = [];
    const events = [];
    const step = (t, phone) => {
      const o = tr.update(t, { phone_in_view: phone, notes_in_view: false });
      warnings.push(...o.warnings);
      events.push(...o.events);
    };
    step(0, true); step(1000, true); // 1 s glimpse...
    step(2000, false); step(3000, false); step(4000, false); step(5000, false);
    expect(warnings).toEqual([]);
    expect(events).toEqual([]); // ...is not recorded
    for (let t = 10000; t <= 16000; t += 1000) step(t, true);
    for (let t = 17000; t <= 21000; t += 1000) step(t, false);
    expect(warnings.map((w) => w.type)).toEqual(["phone_in_view"]);
    expect(warnings[0].message).toMatch(/phone/);
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ event_type: "phone_in_view", t_ms: 10000, duration_ms: 6000 });
  });
});
