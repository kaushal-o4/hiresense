// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/live/notificationStream.js
//
// FILE PURPOSE:
// Keeps one live connection per browser tab to receive 'new notification' signals from the server.
//
// WHAT THIS FILE DOES:
// 1. Opens GET /api/notifications/stream (Server-Sent Events) with the login cookie.
// 2. Tells subscribers to re-fetch notifications when a signal arrives.
// 3. Reconnects with exponential backoff (1-60 s) and polls every 30 s while disconnected.
// 4. Shares one connection between the header bell and the Notifications page.
//
// HOW THIS FILE WORKS:
// NotificationStream wraps EventSource; subscribeNotifications() adds a listener and returns an
// unsubscribe function.
//
// IMPORTANT FUNCTIONS:
//    - subscribeNotifications()
//        Subscribe to change signals.
//    - onNotificationStatus()
//        Subscribe to connection status.
//    - backoffDelay()
//        Reconnect delay with jitter.
//    - NotificationStream()
//        The shared stream class.
//
// IMPORTANT VARIABLES / STATE:
//    - BACKOFF_MIN_MS
//        1 s
//    - BACKOFF_MAX_MS
//        60 s
//    - POLL_MS
//        30 s polling fallback
//
// INPUT:
// Server signals.
//
// OUTPUT:
// Callbacks to subscribed components.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: apiClient.js
//    Used by: components/AppShellLayout.jsx, pages/Notifications.jsx
//    Tested by: live/notificationStream.test.js
//
// IMPORTANT NOTE:
// Signals carry no content; components re-fetch /notifications so normal access checks apply.
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/*
 * Live notifications: one Server-Sent Events connection per browser tab (GET /api/notifications/stream), shared by
 * every component that subscribes (header bell, Notifications page).
 *
 * The server only sends "something changed" signals (`notification` = a new one arrived, `sync` = read/deleted in
 * another tab); listeners then re-fetch /api/notifications. Listeners are also told to re-fetch when the stream
 * (re)connects, when the tab becomes visible again, and - while the stream is down - by a polling fallback, so a
 * missed signal is never lost for long.
 *
 * Reconnects use exponential backoff with jitter (1 s .. 60 s). A clean server-side end (`bye`, every ~10 min so the
 * login is re-checked) reconnects after a short pause without counting as a failure.
 */

import { apiUrl } from "../apiClient";

export const BACKOFF_MIN_MS = 1000;
export const BACKOFF_MAX_MS = 60000;
export const POLL_MS = 30000;

export function backoffDelay(attempt, random = Math.random) {
  const base = Math.min(BACKOFF_MAX_MS, BACKOFF_MIN_MS * 2 ** Math.max(0, attempt));
  return Math.round(base * (0.75 + random() * 0.5)); // +-25% so many tabs don't reconnect in lockstep
}

export class NotificationStream {
  constructor({ url = apiUrl("/api/notifications/stream"), EventSourceImpl = globalThis.EventSource,
    setTimeoutFn = (...a) => globalThis.setTimeout(...a), clearTimeoutFn = (id) => globalThis.clearTimeout(id),
    setIntervalFn = (...a) => globalThis.setInterval(...a), clearIntervalFn = (id) => globalThis.clearInterval(id),
    random = Math.random, doc = globalThis.document } = {}) {
    Object.assign(this, { url, EventSourceImpl, setTimeoutFn, clearTimeoutFn, setIntervalFn, clearIntervalFn, random, doc });
    this.listeners = new Set();
    this.statusListeners = new Set();
    this.es = null;
    this.attempt = 0;
    this.retryTimer = null;
    this.pollTimer = null;
    this.status = "idle"; // idle | connecting | live | polling
    this.onVisible = () => { if (this.doc?.visibilityState === "visible") this.emit("sync"); };
  }

  subscribe(fn) {
    this.listeners.add(fn);
    if (this.listeners.size === 1) this.start();
    return () => {
      this.listeners.delete(fn);
      if (this.listeners.size === 0) this.stop();
    };
  }

  onStatus(fn) {
    this.statusListeners.add(fn);
    fn(this.status);
    return () => this.statusListeners.delete(fn);
  }

  setStatus(s) {
    if (s === this.status) return;
    this.status = s;
    this.statusListeners.forEach((fn) => fn(s));
  }

  emit(type) {
    this.listeners.forEach((fn) => { try { fn(type); } catch { /* a listener's error must not stop the others */ } });
  }

  start() {
    this.doc?.addEventListener?.("visibilitychange", this.onVisible);
    this.connect();
  }

  stop() {
    this.doc?.removeEventListener?.("visibilitychange", this.onVisible);
    this.closeSource();
    if (this.retryTimer) this.clearTimeoutFn(this.retryTimer);
    this.retryTimer = null;
    this.stopPolling();
    this.attempt = 0;
    this.setStatus("idle");
  }

  closeSource() {
    if (this.es) {
      this.es.onerror = null;
      this.es.close();
      this.es = null;
    }
  }

  connect() {
    this.retryTimer = null;
    if (!this.EventSourceImpl) { // very old browser: polling only
      this.startPolling();
      return;
    }
    this.closeSource();
    this.setStatus(this.pollTimer ? "polling" : "connecting");
    let es;
    try {
      es = new this.EventSourceImpl(this.url, { withCredentials: true });
    } catch {
      this.fail();
      return;
    }
    this.es = es;
    es.addEventListener("ready", () => {
      this.attempt = 0;
      this.stopPolling();
      this.setStatus("live");
      this.emit("sync"); // catch up on anything that happened while disconnected
    });
    es.addEventListener("notification", () => this.emit("notification"));
    es.addEventListener("sync", () => this.emit("sync"));
    es.addEventListener("bye", () => { // planned end: reconnect soon, not a failure
      this.closeSource();
      this.schedule(BACKOFF_MIN_MS);
    });
    es.onerror = () => this.fail();
  }

  fail() {
    // We manage retries ourselves (EventSource would retry forever on network errors and never on HTTP 401).
    this.closeSource();
    this.startPolling();
    this.schedule(backoffDelay(this.attempt, this.random));
    this.attempt += 1;
  }

  schedule(ms) {
    if (this.listeners.size === 0) return;
    if (this.retryTimer) this.clearTimeoutFn(this.retryTimer);
    this.retryTimer = this.setTimeoutFn(() => this.connect(), ms);
  }

  startPolling() {
    if (this.pollTimer) return;
    this.setStatus("polling");
    this.pollTimer = this.setIntervalFn(() => this.emit("sync"), POLL_MS);
  }

  stopPolling() {
    if (this.pollTimer) this.clearIntervalFn(this.pollTimer);
    this.pollTimer = null;
  }
}

let shared = null;

/** The tab-wide stream. `fn(type)` is called with "notification" or "sync"; returns an unsubscribe function. */
export function subscribeNotifications(fn) {
  shared = shared || new NotificationStream();
  return shared.subscribe(fn);
}

/** Connection state of the tab-wide stream: "idle" | "connecting" | "live" | "polling". Returns unsubscribe. */
export function onNotificationStatus(fn) {
  shared = shared || new NotificationStream();
  return shared.onStatus(fn);
}
