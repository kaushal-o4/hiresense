// Microphone capture for one answer at a time. The microphone is opened when recording starts and fully
// released when it stops (the browser's mic indicator turns off between answers). Audio stays in memory and is
// sent once, as a 16 kHz mono WAV, to this app's own backend for local transcription.

const WORKLET = `
class PcmCapture extends AudioWorkletProcessor {
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) this.port.postMessage(ch.slice(0));
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
export function vadStep(st, level, dtMs, { threshold = 0.012, silenceMs = 3500, noSpeechMs = 12000, minSpeechMs = 300, minAnswerMs = 0 } = {}) {
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
   */
  async start(opts = {}) {
    if (this.active) return;
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("This browser cannot access a microphone.");
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      });
    } catch (e) {
      if (e.name === "NotAllowedError") throw new Error("Microphone permission was denied. Allow it in the browser's address bar, or type your answer.");
      if (e.name === "NotFoundError") throw new Error("No microphone was found. Connect one, or type your answer.");
      throw new Error(`The microphone could not be started (${e.name}).`);
    }
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
    let segSpeechMs = 0;
    let fired = false;
    this.node.port.onmessage = (e) => {
      if (!this.active) return;
      const chunk = e.data;
      this.chunks.push(chunk);
      const level = rms(chunk);
      opts.onLevel?.(level);
      const dt = (chunk.length / this.ctx.sampleRate) * 1000;
      const r = vadStep(vad, level, dt, { silenceMs: opts.silenceMs || 3500, noSpeechMs: opts.noSpeechMs || 12000,
        minAnswerMs: opts.minAnswerMs || 0 });
      if (r === "speech") segSpeechMs += dt;
      if (r === "no_speech") opts.onNoSpeech?.();
      if (!fired && r === "silence_stop") { fired = true; opts.onSilence?.(); }
      if (!fired && vad.elapsed >= maxMs) { fired = true; opts.onMax?.(); }
      if (!fired && opts.onSegment && vad.quietMs >= segPause && segSpeechMs >= 1500) {
        const pending = this.chunks.length - this.cutAt;
        const pendingMs = pending * dt;
        if (pendingMs >= minSeg) {
          const clip = this._clip(this.cutAt, this.chunks.length);
          this.cutAt = this.chunks.length;
          segSpeechMs = 0;
          opts.onSegment({ ...clip, index: this.segments++ });
        }
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
   * Stops recording, releases the microphone and returns {wav, seconds, segments}.
   * tailOnly: only the audio after the last segment handed to onSegment (the rest is already being transcribed).
   */
  async stop({ tailOnly = false } = {}) {
    if (!this.active) return null;
    this.active = false;
    const clip = { ...this._clip(tailOnly ? this.cutAt : 0, this.chunks.length), segments: this.segments };
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
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close();
    this.stream = null;
    this.ctx = null;
    this.node = null;
    this.chunks = [];
  }
}
