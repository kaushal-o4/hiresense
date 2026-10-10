// Sends integrity events to the server in small batches. Only the event record is sent (type, interview-relative
// time, duration, agreement ratio) - never images, video or face measurements.
import { post } from "../api";

export class EventReporter {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.queue = [];
    this.timer = setInterval(() => this.flush(), 8000);
    this.stopped = false;
  }

  add(event) {
    if (this.stopped || !event) return;
    this.queue.push(event);
    if (this.queue.length >= 10) this.flush();
  }

  async flush() {
    if (!this.queue.length) return;
    const events = this.queue.splice(0, 50);
    try {
      await post(`/student/interviews/${this.sessionId}/integrity-events`, { events });
    } catch (e) {
      if (e.status === 0) this.queue.unshift(...events); // offline: try again later; other errors are dropped
    }
  }

  async close() {
    clearInterval(this.timer);
    await this.flush();
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
