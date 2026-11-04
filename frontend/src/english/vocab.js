/*
 * Pure helpers for the English word list, review session and daily plan (no React, unit-tested in vocab.test.js).
 * The server (backend/app/services/english_vocab.py) owns the Leitner rules; this file only runs the review session
 * on screen and formats what the server sends.
 */

export const BOX_LABELS = { 1: "New", 2: "Learning", 3: "Getting there", 4: "Learned", 5: "Almost mastered" };

export function boxLabel(box, mastered = false) {
  if (mastered) return "Mastered";
  return BOX_LABELS[box] || BOX_LABELS[1];
}

/** "Due now", "Due tomorrow", "Due in 4 days" from an ISO date. */
export function dueText(dueAt, now = new Date()) {
  if (!dueAt) return "";
  const ms = new Date(dueAt).getTime() - now.getTime();
  if (ms <= 0) return "Due now";
  const days = Math.ceil(ms / 86400000);
  return days <= 1 ? "Due tomorrow" : `Due in ${days} days`;
}

export function planSummary(plan) {
  const items = plan?.items || [];
  const done = items.filter((i) => i.done).length;
  const total = items.length;
  return { done, total, percent: total ? Math.round((100 * done) / total) : 0, allDone: total > 0 && done === total };
}

/*
 * Review session state. A card answered "not yet" is shown once more at the end of the session so the student
 * sees the right answer again while it is fresh. That repeat is practice only: it is not sent to the server
 * (the card is already back in box 1 and due tomorrow).
 */
export function startReview(cards) {
  return {
    queue: (cards || []).map((c) => ({ card: c, repeat: false })), index: 0, flipped: false,
    knew: 0, notYet: 0, mastered: 0,
  };
}

export const currentCard = (s) => s.queue[s.index] || null;
export const isFinished = (s) => s.index >= s.queue.length;

export function flip(s) {
  return isFinished(s) ? s : { ...s, flipped: !s.flipped };
}

/** Returns { state, send }: send is true when this answer should be posted to the server. */
export function answer(s, knew, { masteredNow = false } = {}) {
  const cur = currentCard(s);
  if (!cur) return { state: s, send: false };
  const queue = !knew && !cur.repeat ? [...s.queue, { card: cur.card, repeat: true }] : s.queue;
  const counted = !cur.repeat;
  return {
    send: counted,
    state: {
      ...s, queue, index: s.index + 1, flipped: false,
      knew: s.knew + (counted && knew ? 1 : 0),
      notYet: s.notYet + (counted && !knew ? 1 : 0),
      mastered: s.mastered + (masteredNow ? 1 : 0),
    },
  };
}

export function reviewProgress(s) {
  const firstPass = s.queue.filter((q) => !q.repeat).length;
  const answered = Math.min(s.knew + s.notYet, firstPass);
  return { answered, total: firstPass, repeatsLeft: s.queue.slice(s.index).filter((q) => q.repeat).length };
}

/** Rows for the score-trend chart: overall 0-100 and the four skills (0-10) scaled to 0-100. */
export function trendRows(trend) {
  return (trend || []).map((t, i) => ({
    date: t.date || `#${i + 1}`,
    overall: t.overall,
    ...Object.fromEntries(["grammar", "vocabulary", "fluency", "sentence_formation"]
      .map((k) => [k, t[k] == null ? null : Math.round(t[k] * 10)])),
  }));
}
