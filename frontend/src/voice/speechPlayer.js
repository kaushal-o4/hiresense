// Plays the interviewer's voice and exposes the current mouth shape for the avatar.
//
// Main path: audio from the local Kokoro engine + its phoneme timeline. The mouth shape is looked up against the
// AudioContext clock (the same clock the audio is played on) and scaled by the live audio volume, so the lips
// follow the sound and close when it stops.
// Fallback: the browser's built-in voice (speechSynthesis). It gives no phoneme timing, so the mouth uses an
// APPROXIMATE letter-based animation started at each word boundary. The UI labels this mode.
// Pause/resume: `pause()` suspends the audio clock (local voice) or speechSynthesis, so the mouth - which is
// computed from the playback position - freezes too, and `resume()` continues from the same place.
// Streaming: `startQueue()` plays sentences as they arrive (see speechQueue.js) - the first sentence starts while
// later ones are still being generated, in order, never overlapping, with no added pauses between them.
import { SpeechQueue } from "./speechQueue";
import { amplitudeFactor, approximateVisemes, mouthAt, visemeWeightsAt } from "./visemes";

function b64ToArrayBuffer(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

// Browsers don't expose a voice's gender, so it is guessed from common voice names (Windows, macOS, Chrome).
const FEMALE = /female|zira|aria|jenny|hazel|susan|libby|sonia|samantha|victoria|karen|moira|tessa|serena|kate|google uk english female|google us english/i;
const MALE = /\bmale\b|david|mark|guy|george|ryan|thomas|daniel|alex|fred|oliver|arthur|google uk english male/i;

/** Best installed voice for a language and (optional) gender; null = let the browser choose. */
export function pickBrowserVoice(voices, lang = "en-US", gender = null) {
  const english = voices.filter((v) => /^en/i.test(v.lang));
  if (!english.length) return null;
  const sameLang = english.filter((v) => v.lang.replace("_", "-").toLowerCase() === lang.toLowerCase());
  const fits = (v) => (gender === "male" ? MALE.test(v.name) && !/female/i.test(v.name)
    : gender === "female" ? FEMALE.test(v.name) : true);
  return sameLang.find(fits) || english.find(fits) || sameLang[0] || null;
}

export class SpeechPlayer {
  constructor() {
    this.ctx = null;
    this.analyser = null;
    this.source = null;
    this.timeline = [];
    this.mode = null; // "phoneme" | "approx" | null
    this.paused = false;
    this.startAt = 0;
    this.token = 0;
    this.finish = null;
    this.levelBuf = new Float32Array(512);
    this.q = null; // active SpeechQueue (streaming playback)
  }

  // ------------------------------------------------------------------ streaming queue

  /**
   * Start streamed playback. Returns a promise resolving {stopped} when every lane is closed and played.
   * opts.browser: options for browser-voice segments; opts.onFirstAudio(): called when the first sound starts.
   */
  startQueue(lanes, opts = {}) {
    this.stop();
    this.unlock();
    const q = new SpeechQueue(lanes);
    this.q = q;
    this.qOpts = opts;
    this.qFirst = false;
    this.qPlaying = false;
    return new Promise((resolve) => { q.resolve = resolve; });
  }

  get queueActive() {
    return this.q !== null;
  }

  queueAdd(lane, index, text) { if (this.q) { this.q.add(lane, index, text); this._advance(); } }

  queueFill(lane, index, payload) { if (this.q) { this.q.fill(lane, index, payload); this._advance(); } }

  queueBrowserFrom(lane, index) { if (this.q) { this.q.browserFrom(lane, index); this._advance(); } }

  queueClose(lane) { if (this.q) { this.q.close(lane); this._advance(); } }

  /** Drop a lane's unplayed sentences (and cut the one playing, if it is from that lane). */
  queueRetract(lane) {
    if (!this.q) return;
    const current = this.q.played[this.q.played.length - 1];
    this.q.retract(lane);
    if (current?.lane === lane && this.qPlaying) this._cutSegment();
  }

  queueText() {
    return this.q ? this.q.fullText() : "";
  }

  _advance() {
    const q = this.q;
    if (!q || this.qPlaying || this.paused) return;
    const n = q.next();
    if (n.state === "wait") return;
    if (n.state === "done") {
      this.q = null;
      q.resolve?.({ stopped: false });
      return;
    }
    this.qPlaying = true;
    const token = ++this.token;
    const ended = () => {
      if (token !== this.token) return;
      this.qPlaying = false;
      this.mode = null;
      this.timeline = [];
      this.source = null;
      this._advance();
    };
    const first = () => {
      if (!this.qFirst) { this.qFirst = true; this.qOpts?.onFirstAudio?.(); }
    };
    if (n.slot.payload.kind === "phoneme") this._playSegment(n.slot.payload.res, token, ended, first);
    else this._playBrowserSegment(n.slot.text, token, ended, first);
  }

  _cutSegment() {
    this.token++;
    if (this.source) { try { this.source.stop(); } catch { /* already stopped */ } }
    if (window.speechSynthesis?.speaking) window.speechSynthesis.cancel();
    this.source = null;
    this.mode = null;
    this.timeline = [];
    this.qPlaying = false;
    this._advance();
  }

  async _playSegment({ audio_wav_b64, visemes }, token, ended, first) {
    let buffer;
    try {
      buffer = await this.ctx.decodeAudioData(b64ToArrayBuffer(audio_wav_b64));
    } catch {
      if (token === this.token) ended(); // undecodable sentence: skip it rather than stall
      return;
    }
    if (token !== this.token) return;
    const src = this.ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(this.analyser);
    this.source = src;
    this.duration = buffer.duration;
    this.timeline = visemes || [];
    this.mode = "phoneme";
    src.onended = () => ended();
    this.startAt = this.ctx.currentTime + 0.02;
    src.start(this.startAt);
    first();
  }

  _playBrowserSegment(text, token, ended, first) {
    if (!window.speechSynthesis || !text) { ended(); return; }
    const o = this.qOpts?.browser || {};
    const u = new SpeechSynthesisUtterance(text);
    u.lang = o.lang || "en-US";
    u.rate = o.rate || 1;
    u.pitch = o.pitch || 1;
    const voice = pickBrowserVoice(window.speechSynthesis.getVoices?.() || [], u.lang, o.gender || null);
    if (voice) u.voice = voice;
    const t0 = performance.now();
    this.startAt = t0;
    this.timeline = [];
    this.mode = "approx";
    this.textLength = text.length;
    this.charIndex = 0;
    u.onstart = () => first();
    u.onboundary = (e) => {
      if (token !== this.token || (e.name && e.name !== "word")) return;
      this.charIndex = e.charIndex;
      this.timeline = approximateVisemes(text.slice(e.charIndex).split(/\s/)[0], (performance.now() - t0) / 1000, u.rate);
    };
    u.onend = () => ended();
    u.onerror = () => ended();
    window.speechSynthesis.speak(u);
  }

  /** Must be called from a user gesture (e.g. the Start button) so the browser allows audio. */
  unlock() {
    if (!this.ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      this.ctx = new Ctx();
      this.analyser = this.ctx.createAnalyser();
      this.analyser.fftSize = 512;
      this.analyser.connect(this.ctx.destination);
    }
    if (this.ctx.state === "suspended") this.ctx.resume();
  }

  get speaking() {
    return this.mode !== null || this.q !== null;
  }

  /** Play Kokoro audio. Resolves {stopped} when playback ends or is interrupted. Never overlaps. */
  async play({ audio_wav_b64, visemes }) {
    this.stop();
    this.unlock();
    const token = ++this.token;
    const buffer = await this.ctx.decodeAudioData(b64ToArrayBuffer(audio_wav_b64));
    if (token !== this.token) return { stopped: true };
    return new Promise((resolve) => {
      const src = this.ctx.createBufferSource();
      src.buffer = buffer;
      src.connect(this.analyser);
      this.source = src;
      this.duration = buffer.duration;
      this.timeline = visemes || [];
      this.mode = "phoneme";
      this.finish = (stopped) => {
        if (this.source === src) { this.source = null; this.mode = null; this.timeline = []; }
        resolve({ stopped });
      };
      src.onended = () => token === this.token && this.finish?.(false);
      this.startAt = this.ctx.currentTime + 0.05;
      src.start(this.startAt);
    });
  }

  /** Fallback: browser voice with approximate mouth movement. `gender` picks a matching installed voice if any. */
  playBrowser(text, { lang = "en-US", rate = 1, pitch = 1, gender = null } = {}) {
    this.stop();
    const token = ++this.token;
    return new Promise((resolve, reject) => {
      if (!window.speechSynthesis) return reject(new Error("This browser cannot speak text aloud."));
      const u = new SpeechSynthesisUtterance(text);
      u.lang = lang;
      u.rate = rate;
      u.pitch = pitch;
      const voice = pickBrowserVoice(window.speechSynthesis.getVoices?.() || [], lang, gender);
      if (voice) u.voice = voice;
      const t0 = performance.now();
      this.startAt = t0;
      this.timeline = [];
      this.mode = "approx";
      this.textLength = text.length;
      this.charIndex = 0;
      u.onboundary = (e) => {
        if (e.name && e.name !== "word") return;
        this.charIndex = e.charIndex;
        const word = text.slice(e.charIndex).split(/\s/)[0];
        this.timeline = approximateVisemes(word, (performance.now() - t0) / 1000, rate);
      };
      const done = (stopped) => { if (token === this.token) { this.mode = null; this.timeline = []; } resolve({ stopped }); };
      this.finish = done;
      u.onend = () => done(false);
      u.onerror = (e) => (e.error === "interrupted" || e.error === "canceled" ? done(true) : reject(new Error(e.error)));
      window.speechSynthesis.speak(u);
    });
  }

  /** Pause the current utterance (true if something was paused). The mouth closes while paused. */
  pause() {
    if ((this.mode === null && this.q === null) || this.paused) return false;
    this.paused = true;
    if (this.mode === "phoneme") this.ctx.suspend();
    else if (this.mode === "approx") window.speechSynthesis?.pause();
    return true; // between two streamed sentences: nothing new starts until resume()
  }

  resume() {
    if (!this.paused) return;
    this.paused = false;
    if (this.mode === "phoneme") this.ctx.resume();
    else if (this.mode === "approx") window.speechSynthesis?.resume();
    this._advance();
  }

  stop() {
    if (this.paused) {
      this.paused = false;
      if (this.ctx?.state === "suspended") this.ctx.resume();
      window.speechSynthesis?.resume?.();
    }
    const q = this.q;
    this.q = null;
    this.qPlaying = false;
    q?.resolve?.({ stopped: true });
    this.token++;
    if (this.source) {
      try { this.source.stop(); } catch { /* already stopped */ }
    }
    if (window.speechSynthesis?.speaking) window.speechSynthesis.cancel();
    const fin = this.finish;
    this.finish = null;
    this.source = null;
    this.mode = null;
    this.timeline = [];
    fin?.(true);
  }

  /** How far through the current utterance we are (0-1), for subtitles; null when silent. */
  progress() {
    let p = null;
    if (this.mode === "phoneme") {
      p = Math.min(1, Math.max(0, (this.ctx.currentTime - this.startAt) / (this.duration || 1)));
    } else if (this.mode === "approx") p = Math.min(1, this.charIndex / (this.textLength || 1));
    if (this.q) {
      // streamed: position within the whole text so far (the subtitle line shows all of it)
      const total = this.q.fullText().length || 1;
      const { start, length } = this.q.currentSpan();
      return p === null ? null : Math.min(1, (start + p * length) / total);
    }
    return p;
  }

  /** Current audio level (RMS) of the interviewer's voice. */
  level() {
    if (this.mode !== "phoneme" || !this.analyser) return 0;
    this.analyser.getFloatTimeDomainData(this.levelBuf);
    let sum = 0;
    for (const v of this.levelBuf) sum += v * v;
    return Math.sqrt(sum / this.levelBuf.length);
  }

  /** Target mouth shape right now, or null when not speaking. Called by the avatar every animation frame. */
  getMouth() {
    if (this.paused) return null;
    if (this.mode === "phoneme") {
      const t = this.ctx.currentTime - this.startAt;
      const m = mouthAt(this.timeline, t);
      const amp = amplitudeFactor(this.level());
      return { ...m, open: m.open * amp, amp };
    }
    if (this.mode === "approx") {
      return { ...mouthAt(this.timeline, (performance.now() - this.startAt) / 1000), amp: 0.6 };
    }
    return null;
  }

  /** Viseme weights right now for the 3D avatar ({} when silent), plus the voice level for head motion. */
  getVisemes() {
    if (this.paused) return null;
    if (this.mode === "phoneme") {
      const amp = amplitudeFactor(this.level());
      return { weights: visemeWeightsAt(this.timeline, this.ctx.currentTime - this.startAt), amp };
    }
    if (this.mode === "approx") {
      return { weights: visemeWeightsAt(this.timeline, (performance.now() - this.startAt) / 1000), amp: 0.6 };
    }
    return null;
  }

  close() {
    this.stop();
    this.ctx?.close();
    this.ctx = null;
  }
}
