import { describe, expect, it } from "vitest";
import { BACKOFF_MAX_MS, BACKOFF_MIN_MS, NotificationStream, POLL_MS, backoffDelay } from "./notificationStream";

class FakeES {
  static all = [];
  constructor(url, opts) {
    Object.assign(this, { url, opts, handlers: {}, closed: false, onerror: null });
    FakeES.all.push(this);
  }
  addEventListener(type, fn) { (this.handlers[type] ||= []).push(fn); }
  fire(type) { (this.handlers[type] || []).forEach((fn) => fn({})); }
  close() { this.closed = true; }
}

function fakeTimers() {
  const t = { now: 0, seq: 0, items: new Map() };
  t.setTimeoutFn = (fn, ms) => { const id = ++t.seq; t.items.set(id, { fn, at: t.now + ms }); return id; };
  t.clearTimeoutFn = (id) => t.items.delete(id);
  t.setIntervalFn = (fn, ms) => { const id = ++t.seq; t.items.set(id, { fn, at: t.now + ms, every: ms }); return id; };
  t.clearIntervalFn = (id) => t.items.delete(id);
  t.advance = (ms) => {
    const end = t.now + ms;
    for (;;) {
      const due = [...t.items.entries()].filter(([, v]) => v.at <= end).sort((a, b) => a[1].at - b[1].at)[0];
      if (!due) break;
      const [id, v] = due;
      t.now = v.at;
      if (v.every) v.at += v.every; else t.items.delete(id);
      v.fn();
    }
    t.now = end;
  };
  return t;
}

function setup() {
  FakeES.all = [];
  const timers = fakeTimers();
  const s = new NotificationStream({ url: "/api/notifications/stream", EventSourceImpl: FakeES, random: () => 0.5,
    doc: null, ...timers });
  const got = [];
  const unsub = s.subscribe((type) => got.push(type));
  return { s, timers, got, unsub, es: () => FakeES.all.at(-1) };
}

describe("backoff", () => {
  it("doubles from 1 s and caps at 60 s", () => {
    const mid = () => 0.5;
    expect(backoffDelay(0, mid)).toBe(BACKOFF_MIN_MS);
    expect(backoffDelay(1, mid)).toBe(2000);
    expect(backoffDelay(3, mid)).toBe(8000);
    expect(backoffDelay(20, mid)).toBe(BACKOFF_MAX_MS);
    expect(backoffDelay(0, () => 0)).toBe(750); // jitter -25%
  });
});

describe("NotificationStream", () => {
  it("connects with credentials on first subscriber and relays signals", () => {
    const { s, got, es } = setup();
    expect(es().opts).toEqual({ withCredentials: true });
    expect(s.status).toBe("connecting");
    es().fire("ready");
    expect(s.status).toBe("live");
    es().fire("notification");
    es().fire("sync");
    expect(got).toEqual(["sync", "notification", "sync"]); // ready -> catch-up sync
  });

  it("falls back to polling and reconnects with growing backoff after errors", () => {
    const { s, timers, got, es } = setup();
    es().onerror();
    expect(s.status).toBe("polling");
    expect(es().closed).toBe(true);
    timers.advance(BACKOFF_MIN_MS);
    expect(FakeES.all).toHaveLength(2);
    es().onerror();
    timers.advance(1999);
    expect(FakeES.all).toHaveLength(2); // second wait is 2 s
    timers.advance(1);
    expect(FakeES.all).toHaveLength(3);
    // still down: polling keeps listeners fresh
    es().onerror();
    got.length = 0;
    timers.advance(POLL_MS);
    expect(got).toContain("sync");
    // recovered: polling stops, backoff resets
    timers.advance(BACKOFF_MAX_MS);
    es().fire("ready");
    expect(s.status).toBe("live");
    expect(s.pollTimer).toBeNull();
    expect(s.attempt).toBe(0);
  });

  it("reconnects quickly after a planned server end", () => {
    const { s, timers, es } = setup();
    es().fire("ready");
    es().fire("bye");
    expect(s.attempt).toBe(0);
    timers.advance(BACKOFF_MIN_MS);
    expect(FakeES.all).toHaveLength(2);
  });

  it("shares one connection and closes it when the last subscriber leaves", () => {
    const { s, unsub, es, timers } = setup();
    const unsub2 = s.subscribe(() => {});
    expect(FakeES.all).toHaveLength(1);
    unsub();
    expect(es().closed).toBe(false);
    unsub2();
    expect(es().closed).toBe(true);
    expect(s.status).toBe("idle");
    timers.advance(BACKOFF_MAX_MS * 2);
    expect(FakeES.all).toHaveLength(1); // no reconnect after stop
  });

  it("polls when EventSource is not available", () => {
    const timers = fakeTimers();
    const s = new NotificationStream({ EventSourceImpl: undefined, doc: null, ...timers });
    const got = [];
    s.subscribe((t) => got.push(t));
    expect(s.status).toBe("polling");
    timers.advance(POLL_MS);
    expect(got).toEqual(["sync"]);
  });
});
