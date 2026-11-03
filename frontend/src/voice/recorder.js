// Microphone capture for one answer at a time. The microphone is opened when recording starts and fully
// released when it stops (the browser's mic indicator turns off between answers). Audio stays in memory and is
// sent as 16 kHz mono WAV pieces (live captions while talking, then the rest) to this app's own backend for local
// transcription.

// Samples are posted in ~21 ms batches (1024 at 48 kHz), not per 128-sample render block: one message per block is
// ~375 main-thread tasks a second, each updating the level meter, which made the 3D avatar stutter while recording.
const WORKLET = `
class PcmCapture extends AudioWorkletProcessor {
  constructor() { super(); this.buf = new Float32Array(1024); this.n = 0; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    let i = 0;
    while (i < ch.length) {
      const take = Math.min(ch.length - i, this.buf.length - this.n);
      this.buf.set(ch.subarray(i, i + take), this.n);
      this.n += take;
      i += take;
      if (this.n === this.buf.length) { this.port.postMessage(this.buf.slice(0)); this.n = 0; }
    }
    return true;
  }
}
registerProcessor("pcm-capture", PcmCapture);`;

/** Average-downsample float samples from `fromRate` to `toRate`. */
export function downsample(samples, fromRate, toRate = 16000) {
  if (fromRate === toRate) return samples;
  const ratio = fromRate / toRate;
  const out = new Float32Array(Math.floor(samples.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(samples.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += samples[j];
    out[i] = sum / Math.max(1, end - start);
  }
  return out;
}

/** 16-bit PCM mono WAV file bytes. */
export function encodeWav(samples, sampleRate = 16000) {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buf);
  const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  str(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); str(8, "WAVE");
  str(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, sampleRate, true); v.setUint32(28, sampleRate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, "data"); v.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Uint8Array(buf);
}

export function rms(chunk) {
  let sum = 0;
  for (const x of chunk) sum += x * x;
  return Math.sqrt(sum / Math.max(1, chunk.length));
}

/**
 * Silence detector state machine, kept pure so it can be tested. Returns "speech" | "silence_stop" | "no_speech" | null.
 * silenceMs: pause that ends the answer (end-of-speech timeout, adjustable by the student).
 * minAnswerMs: total speech needed before a pause may end the answer, so a pause right after the first words
 * (thinking, a slow start) does not cut the student off.
 */
export const VAD_THRESHOLD = 0.012;

export function vadStep(st, level, dtMs, { threshold = VAD_THRESHOLD, silenceMs = 3500, noSpeechMs = 12000, minSpeechMs = 300, minAnswerMs = 0 } = {}) {
  st.elapsed += dtMs;
  if (level > threshold) {
    st.speechMs += dtMs;
    st.quietMs = 0;
    if (st.speechMs >= minSpeechMs) st.started = true;
    return st.started ? "speech" : null;
  }
  st.quietMs += dtMs;
  if (st.started && st.quietMs >= silenceMs && st.speechMs >= minAnswerMs) return "silence_stop";
  if (!st.started && !st.warned && st.elapsed >= noSpeechMs) { st.warned = true; return "no_speech"; }
  return null;
}

export class MicRecorder {
  constructor() {
    this.stream = null;
    this.ctx = null;
    this.node = null;
    this.chunks = [];
    this.active = false;
  }

  /**
   * Opens the microphone and starts recording.
   * opts: onLevel(rms), onSilence() (candidate stopped talking), onNoSpeech(), onMax(), silenceMs, noSpeechMs, maxSeconds,
   *       minAnswerMs, onSegment({wav, seconds, index}) - a finished stretch of speech cut at a short natural pause
   *       (segmentPauseMs) once it is at least minSegmentMs long; used for live partial transcripts, so that after
   *       the student stops only the last piece still needs transcribing.
   *       onInterim({wav, seconds, from, to}) - live captions: the audio after the last segment, handed out every
   *       interimMs while the student talks (and once more right after they pause), unless interimBusy() says the
   *       previous one is still being transcribed. If the latest interim reaches the end of the speech, its text is
   *       the final text of that piece and nothing has to be transcribed after the student stops (see stop()).
   */
  async start(opts = {}) {
    if (this.active) return;
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("This browser cannot access a microphone.");
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      });
    } catch (e) {
      const named = (msg) => Object.assign(new Error(msg), { name: e.name }); // name kept for monitoring (micLost)
      if (e.name === "NotAllowedError") throw named("Microphone permission was denied. Allow it in the browser's address bar, or type your answer.");
      if (e.name === "NotFoundError") throw named("No microphone was found. Connect one, or type your answer.");
      throw named(`The microphone could not be started (${e.name}).`);
    }
    // unplugged / disabled while answering (opts.onEnded); release() clears it so a normal stop does not count
    this.stream.getAudioTracks().forEach((t) => { t.onended = () => { if (this.active) opts.onEnded?.(); }; });
    const Ctx = window.AudioContext || window.webkitAudioContext;
    this.ctx = new Ctx();
    const url = URL.createObjectURL(new Blob([WORKLET], { type: "application/javascript" }));
    await this.ctx.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);
    const src = this.ctx.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.ctx, "pcm-capture");
    this.chunks = [];
    this.cutAt = 0; // chunks before this index were already handed out as segments
    this.segments = 0;
    this.active = true;
    const vad = { elapsed: 0, speechMs: 0, quietMs: 0, started: false, warned: false };
    const maxMs = (opts.maxSeconds || 180) * 1000;
    const segPause = opts.segmentPauseMs || 600;
    const minSeg = opts.minSegmentMs || 4000;
    const interimMs = opts.interimMs || 1200;
    let segSpeechMs = 0;
    let fired = false;
    this.speechTo = 0; // chunk index just after the last loud chunk
    let interimTo = 0; // chunk index the latest interim clip ended at
    this.node.port.onmessage = (e) => {
      if (!this.active) return;
      const chunk = e.data;
      this.chunks.push(chunk);
      const level = rms(chunk);
      const dt = (chunk.length / this.ctx.sampleRate) * 1000;
      opts.onLevel?.(level, dt);
      const r = vadStep(vad, level, dt, { silenceMs: opts.silenceMs || 3500, noSpeechMs: opts.noSpeechMs || 12000,
        minAnswerMs: opts.minAnswerMs || 0 });
      if (r === "speech") segSpeechMs += dt;
      if (level > VAD_THRESHOLD) this.speechTo = this.chunks.length;
      if (r === "no_speech") opts.onNoSpeech?.();
      if (!fired && r === "silence_stop") { fired = true; opts.onSilence?.(); }
      if (!fired && vad.elapsed >= maxMs) { fired = true; opts.onMax?.(); }
      if (!fired && opts.onSegment && vad.quietMs >= segPause && segSpeechMs >= 1500) {
        const pending = this.chunks.length - this.cutAt;
        const pendingMs = pending * dt;
        if (pendingMs >= minSeg) {
          const clip = { ...this._clip(this.cutAt, this.chunks.length), from: this.cutAt, to: this.chunks.length };
          this.cutAt = this.chunks.length;
          segSpeechMs = 0;
          opts.onSegment({ ...clip, index: this.segments++ });
        }
      }
      // Live caption of the unfinished piece: on a timer while talking, and once at the start of every pause so the
      // caption covers the speech up to its end before the end-of-answer timeout fires.
      const unseen = this.speechTo > Math.max(this.cutAt, interimTo); // speech not covered by the latest interim
      const due = (this.chunks.length - interimTo) * dt >= interimMs || (vad.quietMs >= 300 && unseen);
      if (!fired && opts.onInterim && vad.started && unseen && due && !opts.interimBusy?.()) {
        interimTo = this.chunks.length;
        opts.onInterim({ ...this._clip(this.cutAt, interimTo), from: this.cutAt, to: interimTo });
      }
    };
    src.connect(this.node);
    // Connect through a muted gain so the worklet keeps running without playing the mic back to the speakers.
    const mute = this.ctx.createGain();
    mute.gain.value = 0;
    this.node.connect(mute).connect(this.ctx.destination);
    this.speechDetected = () => vad.started;
  }

  _clip(from, to) {
    const parts = this.chunks.slice(from, to);
    const total = parts.reduce((a, c) => a + c.length, 0);
    const all = new Float32Array(total);
    let o = 0;
    for (const c of parts) { all.set(c, o); o += c.length; }
    const pcm = downsample(all, this.ctx.sampleRate, 16000);
    return { wav: encodeWav(pcm, 16000), seconds: pcm.length / 16000 };
  }

  /**
   * Stops recording, releases the microphone and returns {wav, seconds, segments, from, speechTo}.
   * tailOnly: only the audio after the last segment handed to onSegment (the rest is already being transcribed).
   * from/speechTo (chunk indexes): an interim clip with the same `from` and `to >= speechTo` already holds all of
   * this clip's speech (the rest is silence), so its text can be used instead of transcribing the clip again.
   */
  async stop({ tailOnly = false } = {}) {
    if (!this.active) return null;
    this.active = false;
    const from = tailOnly ? this.cutAt : 0;
    const clip = { ...this._clip(from, this.chunks.length), segments: this.segments, from, speechTo: this.speechTo };
    this.release();
    return clip;
  }

  /** Discards the recording and releases the microphone. */
  cancel() {
    this.active = false;
    this.release();
  }

  release() {
    this.node?.port && (this.node.port.onmessage = null);
    this.stream?.getAudioTracks().forEach((t) => { t.onended = null; });
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close();
    this.stream = null;
    this.ctx = null;
    this.node = null;
    this.chunks = [];
  }
}
