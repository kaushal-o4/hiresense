// Sends integrity events to the server in small batches. Only the event record is sent (type, interview-relative
// time, duration, agreement ratio, whitelisted details) - never images, video, audio or face measurements.
//
// Reliability: every event gets a client id, so a batch can be re-sent safely (the server stores each id once).
// Unsent events are kept in sessionStorage, so a reload or crash does not lose them (the reloaded page sends them),
// and the page-close handler flushes with a keepalive request. Network failures are reported to onConnection.
import { post, put } from "../api";

const storeKey = (id) => `hs-integrity-queue-${id}`;
const store = {
  get(id) { try { return JSON.parse(sessionStorage.getItem(storeKey(id)) || "[]"); } catch { return []; } },
  set(id, q) { try { if (q.length) sessionStorage.setItem(storeKey(id), JSON.stringify(q)); else sessionStorage.removeItem(storeKey(id)); } catch { /* storage unavailable */ } },
};

export function eventId() {
  try { if (crypto?.randomUUID) return crypto.randomUUID().replace(/-/g, "").slice(0, 32); } catch { /* older browser */ }
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
}

export class EventReporter {
  /** onConnection(ok: boolean, reason) - called when sending fails because the server is unreachable, and when it works again. */
  constructor(sessionId, { onConnection, intervalMs = 8000 } = {}) {
    this.sessionId = sessionId;
    this.onConnection = onConnection;
    this.queue = store.get(sessionId); // left over from a reload / crash of this interview
    this.timer = setInterval(() => this.flush(), intervalMs);
    this.stopped = false;
    this.sending = false;
    this._hide = () => this.flushOnExit();
    window.addEventListener("pagehide", this._hide);
  }

  add(event) {
    if (this.stopped || !event) return;
    this.queue.push({ client_event_id: eventId(), ...event });
    store.set(this.sessionId, this.queue);
    if (this.queue.length >= 10) this.flush();
  }

  async flush() {
    if (!this.queue.length || this.sending) return; // one request at a time (no concurrent duplicates)
    this.sending = true;
    const events = this.queue.slice(0, 50);
    try {
      await post(`/student/interviews/${this.sessionId}/integrity-events`, { events });
      this.queue.splice(0, events.length);
      this.onConnection?.(true);
    } catch (e) {
      if (e.status === 0) this.onConnection?.(false, "server_unreachable"); // keep them and try again later
      else if (e.status !== 429) this.queue.splice(0, events.length); // rejected (finished, withdrawn): drop
    } finally {
      this.sending = false;
      store.set(this.sessionId, this.queue);
    }
  }

  /** Cumulative attention totals of this monitor run (idempotent; a lost update is covered by the next one). */
  async sendAttention(snapshot) {
    if (this.stopped) return;
    this.latestAttention = snapshot;
    try {
      await put(`/student/interviews/${this.sessionId}/attention`, snapshot);
      this.onConnection?.(true);
    } catch (e) {
      if (e.status === 0) this.onConnection?.(false, "server_unreachable");
    }
  }

  /** Page closing: send what is left with a request the browser completes after the page is gone. */
  flushOnExit() {
    if (this.latestAttention) {
      try {
        fetch(`/api/student/interviews/${this.sessionId}/attention`, {
          method: "PUT", credentials: "include", keepalive: true, headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.latestAttention),
        }).catch(() => {});
      } catch { /* the next page sends fresh totals */ }
    }
    if (!this.queue.length) return;
    try {
      fetch(`/api/student/interviews/${this.sessionId}/integrity-events`, {
        method: "POST", credentials: "include", keepalive: true, headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: this.queue.slice(0, 50) }),
      }).catch(() => {});
    } catch { /* the queue stays in sessionStorage and is sent by the next page */ }
  }

  async close() {
    clearInterval(this.timer);
    window.removeEventListener("pagehide", this._hide);
    for (let i = 0; i < 10 && this.queue.length; i++) { // a send may be in flight; then up to a few batches
      if (this.sending) await new Promise((r) => setTimeout(r, 200));
      else await this.flush();
    }
    this.stopped = true;
  }
}

/** Browser-measured timings for the performance dashboard (names are whitelisted on the server). */
const pending = [];
let flushTimer = null;
export function reportMetric(metric, durationMs, meta = {}, ok = true) {
  if (!Number.isFinite(durationMs) || durationMs < 0) return;
  pending.push({ metric, duration_ms: Math.round(durationMs), ok, meta });
  clearTimeout(flushTimer);
  flushTimer = setTimeout(() => {
    const metrics = pending.splice(0, 50);
    post("/perf/client", { metrics }).catch(() => {});
  }, 3000);
}
