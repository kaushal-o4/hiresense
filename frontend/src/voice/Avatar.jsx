import { useEffect, useRef } from "react";
import { SHAPES, lerpShape, mouthGeometry } from "./visemes";

// Original illustrated interviewer ("Aria"). Drawn in SVG and animated every frame by writing attributes
// directly (no React re-render per frame). Mouth shapes come from `getMouth()` (the speech player's lip-sync
// clock); everything else - blinking, eye contact, head motion and expressions - is driven by `mode`.

const EXPRESSION = {
  idle: { smile: 0.35, brow: 0, browTilt: 0, tilt: 0, gaze: [0, 0] },
  speaking: { smile: 0.25, brow: 0.5, browTilt: 0, tilt: 0, gaze: [0, 0] },
  listening: { smile: 0.55, brow: 1.6, browTilt: 0, tilt: 2.2, gaze: [0, 0] },
  thinking: { smile: 0.1, brow: 0.8, browTilt: 2.2, tilt: -1.8, gaze: [2.6, -2.6] },
  // warm, smiling delivery (still lip-synced) for praise and reassurance
  encouraging: { smile: 0.75, brow: 1.2, browTilt: 0, tilt: 1.5, gaze: [0, 0] },
};
const TALKING = new Set(["speaking", "encouraging", "greeting", "probing", "feedback"]);

// Colours of the 2D fallback (used only when WebGL is unavailable). The drawing itself is Aria's; other interviewers
// get their own hair and clothing colours so they stay recognisable.
const PALETTES = {
  aria: { hair: ["#f6e2a8", "#e2c27c", "#bf9654"], hairDark: ["#d7b46f", "#a87f44"], clothes: ["#b4cde4", "#8eadcc"], brow: "#a98450" },
  victor: { hair: ["#c9c6c1", "#a8a39c", "#7f7a73"], hairDark: ["#9c978f", "#6f6a63"], clothes: ["#5b6470", "#3c434d"], brow: "#7c766e" },
  marcus: { hair: ["#4a3b2e", "#33281f", "#1f1813"], hairDark: ["#3a2e24", "#1f1813"], clothes: ["#3a3f47", "#22262c"], brow: "#2b211a" },
  elena: { hair: ["#3b2a22", "#2a1d17", "#170f0b"], hairDark: ["#2e211a", "#170f0b"], clothes: ["#2f3442", "#1c202b"], brow: "#2a1d17" },
};

const face = (jaw) =>
  `M200 126 C250 126 284 160 284 218 C284 262 271 292 252 314 C236 331 221 ${341 + jaw} 200 ${343 + jaw} ` +
  `C179 ${343 + jaw} 164 331 148 314 C129 292 116 262 116 218 C116 160 150 126 200 126 Z`;

const EYE_L = "M145 223 C152 208.5 180 208.5 187 222 C180 231 152 231.5 145 223 Z";
const EYE_R = "M213 222 C220 208.5 248 208.5 255 223 C248 231.5 220 231 213 222 Z";

function smooth(cur, target, rate, dt) {
  return cur + (target - cur) * (1 - Math.exp(-rate * dt));
}

export default function Avatar({ getMouth, mode = "idle", className = "", palette = "aria" }) {
  const pal = PALETTES[palette] || PALETTES.aria;
  const r = useRef({});
  const modeRef = useRef(mode);
  modeRef.current = mode;

  useEffect(() => {
    const el = r.current;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const st = {
      mouth: { ...SHAPES.sil }, smile: 0.35, brow: 0, browTilt: 0, tilt: 0, gx: 0, gy: 0,
      saccade: [0, 0], nextSaccade: 0, blink: 0, nextBlink: 1.5, blinkStart: -1, nod: 0, nextNod: 3,
    };
    let last = performance.now();
    let raf;
    const loop = (now) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const t = now / 1000;
      const m = modeRef.current;
      const ex = EXPRESSION[m] || EXPRESSION.idle;

      // ---- mouth (lip sync while speaking, otherwise relaxed / slight smile)
      const talking = TALKING.has(m);
      const target = (talking && getMouth?.()) || SHAPES.sil;
      st.mouth = lerpShape(st.mouth, target, 1 - Math.exp(-28 * dt));
      const amp = target.amp ?? 0;

      // ---- expression
      st.smile = smooth(st.smile, ex.smile, 4, dt);
      st.brow = smooth(st.brow, ex.brow + (talking ? amp * 1.2 : 0), 6, dt);
      st.browTilt = smooth(st.browTilt, ex.browTilt, 4, dt);
      st.tilt = smooth(st.tilt, ex.tilt, 2.5, dt);

      // ---- eyes: look at the camera (centre) with tiny natural saccades
      if (t > st.nextSaccade) {
        st.saccade = m === "thinking" ? [Math.random() * 1.2, -Math.random()] : [(Math.random() - 0.5) * 1.4, (Math.random() - 0.5) * 0.9];
        st.nextSaccade = t + 0.7 + Math.random() * 2.2;
      }
      st.gx = smooth(st.gx, ex.gaze[0] + st.saccade[0], 18, dt);
      st.gy = smooth(st.gy, ex.gaze[1] + st.saccade[1], 18, dt);

      // ---- blinking: every 2-6 s, ~140 ms, sometimes double
      if (st.blinkStart < 0 && t > st.nextBlink) st.blinkStart = t;
      if (st.blinkStart >= 0) {
        const p = (t - st.blinkStart) / 0.14;
        st.blink = p < 0.5 ? p * 2 : Math.max(0, 2 - p * 2);
        if (p >= 1) {
          st.blinkStart = -1;
          st.blink = 0;
          st.nextBlink = t + (Math.random() < 0.15 ? 0.25 : 2 + Math.random() * 4);
        }
      }

      // ---- head motion: gentle sway + breathing; small nods while listening
      if (m === "listening" && t > st.nextNod) { st.nod = 1; st.nextNod = t + 3.5 + Math.random() * 3; }
      st.nod = Math.max(0, st.nod - dt * 1.6);
      const nodY = Math.sin((1 - st.nod) * Math.PI) * st.nod * 3;
      const k = reduced ? 0.2 : 1;
      const rot = k * (Math.sin(t * 0.55) * 0.9 + Math.sin(t * 1.7) * 0.35 + (talking ? Math.sin(t * 3.1) * amp * 1.6 : 0)) + st.tilt;
      const dy = k * (Math.sin(t * 0.9) * 0.9) + nodY;
      const breath = k * Math.sin(t * 1.25) * 0.8;

      // ---- write to the SVG
      const g = mouthGeometry(st.mouth, 200, 304, st.smile);
      el.head.setAttribute("transform", `translate(0 ${dy.toFixed(2)}) rotate(${rot.toFixed(2)} 200 330)`);
      el.body.setAttribute("transform", `translate(0 ${breath.toFixed(2)})`);
      el.face.setAttribute("d", face(g.jawDrop));
      el.upper.setAttribute("d", g.upper);
      el.lower.setAttribute("d", g.lower);
      el.inner.setAttribute("d", g.inner);
      el.clip.setAttribute("d", g.inner);
      el.teeth.setAttribute("x", g.teeth.x.toFixed(1));
      el.teeth.setAttribute("y", g.teeth.y.toFixed(1));
      el.teeth.setAttribute("width", g.teeth.w.toFixed(1));
      el.teeth.setAttribute("height", Math.max(0, g.teeth.h).toFixed(1));
      el.tongue.setAttribute("cy", g.tongue.cy.toFixed(1));
      el.tongue.setAttribute("rx", g.tongue.rx.toFixed(1));
      el.tongue.setAttribute("ry", g.tongue.ry.toFixed(1));
      el.chin.setAttribute("transform", `translate(0 ${g.jawDrop.toFixed(2)})`);
      for (const side of ["L", "R"]) {
        el[`iris${side}`].setAttribute("transform", `translate(${st.gx.toFixed(2)} ${st.gy.toFixed(2)})`);
        el[`lid${side}`].setAttribute("height", (2 + st.blink * 22).toFixed(1));
        el[`lash${side}`].setAttribute("transform", `translate(0 ${(st.blink * 17).toFixed(1)})`);
      }
      el.browL.setAttribute("transform", `translate(0 ${(-st.brow).toFixed(2)}) rotate(${(-st.browTilt * 0.3).toFixed(2)} 166 202)`);
      el.browR.setAttribute("transform", `translate(0 ${(-st.brow - st.browTilt).toFixed(2)}) rotate(${(st.browTilt).toFixed(2)} 234 202)`);
      el.cheeks.setAttribute("opacity", (0.18 + st.smile * 0.18).toFixed(2));
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [getMouth]);

  const set = (name) => (node) => { r.current[name] = node; };

  return (
    <svg viewBox="0 0 400 480" className={className} role="img" aria-label={`AI interviewer, ${mode}`} data-avatar-mode={mode}>
      <defs>
        <linearGradient id="av-bg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#e6edf5" /><stop offset="1" stopColor="#c7d4e3" />
        </linearGradient>
        <radialGradient id="av-skin" cx="0.5" cy="0.42" r="0.62">
          <stop offset="0" stopColor="#fbe1d0" /><stop offset="0.75" stopColor="#f2c7ad" /><stop offset="1" stopColor="#e4ae92" />
        </radialGradient>
        <linearGradient id="av-hair" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={pal.hair[0]} /><stop offset="0.5" stopColor={pal.hair[1]} /><stop offset="1" stopColor={pal.hair[2]} />
        </linearGradient>
        <linearGradient id="av-hair-dark" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={pal.hairDark[0]} /><stop offset="1" stopColor={pal.hairDark[1]} />
        </linearGradient>
        <linearGradient id="av-denim" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={pal.clothes[0]} /><stop offset="1" stopColor={pal.clothes[1]} />
        </linearGradient>
        <radialGradient id="av-iris" cx="0.45" cy="0.4" r="0.6">
          <stop offset="0" stopColor="#9cc0dc" /><stop offset="0.7" stopColor="#5b86ab" /><stop offset="1" stopColor="#36597a" />
        </radialGradient>
        <clipPath id="av-eyeL"><path d={EYE_L} /></clipPath>
        <clipPath id="av-eyeR"><path d={EYE_R} /></clipPath>
        <clipPath id="av-mouth"><path ref={set("clip")} d="" /></clipPath>
      </defs>

      {/* background: soft, out-of-focus office. Drawn wider than the viewBox so it fills wide screens. */}
      <rect x="-700" y="-50" width="1800" height="580" fill="url(#av-bg)" />
      <rect x="-700" y="380" width="1800" height="150" fill="#b7c6d6" opacity="0.45" />
      <rect x="-330" y="70" width="230" height="170" rx="8" fill="#f4f8fc" opacity="0.55" />
      <rect x="-320" y="80" width="105" height="150" fill="#dce7f2" opacity="0.6" /><rect x="-205" y="80" width="95" height="150" fill="#dce7f2" opacity="0.6" />
      <circle cx="60" cy="90" r="40" fill="#fff" opacity="0.35" /><circle cx="340" cy="70" r="28" fill="#fff" opacity="0.3" />
      <rect x="300" y="150" width="70" height="120" rx="6" fill="#b9c8d9" opacity="0.5" />
      <rect x="470" y="120" width="60" height="200" rx="6" fill="#a9bccf" opacity="0.45" />
      <ellipse cx="560" cy="300" rx="40" ry="60" fill="#8fb39a" opacity="0.35" /><rect x="545" y="340" width="30" height="50" fill="#9aa9b8" opacity="0.5" />

      {/* body: neck + denim shirt (breathing) */}
      <g ref={set("body")}>
        <path d="M176 318 L176 372 C186 384 214 384 224 372 L224 318 Z" fill="#eab597" />
        <path d="M176 352 C186 366 214 366 224 352 L224 372 C214 384 186 384 176 372 Z" fill="#d89d80" opacity="0.6" />
        <path d="M30 480 C34 430 62 402 108 392 L170 368 L200 400 L230 368 L292 392 C338 402 366 430 370 480 Z" fill="url(#av-denim)" />
        <path d="M170 368 L148 398 L176 420 L200 400 Z" fill="#c4d8ea" stroke="#86a6c6" strokeWidth="1.2" />
        <path d="M230 368 L252 398 L224 420 L200 400 Z" fill="#c4d8ea" stroke="#86a6c6" strokeWidth="1.2" />
        <path d="M200 400 L200 480" stroke="#7d9dbd" strokeWidth="1.5" />
        {[425, 452].map((y) => <circle key={y} cx="206" cy={y} r="2.4" fill="#e8eef5" stroke="#7d9dbd" strokeWidth="0.8" />)}
        <path d="M110 430 L160 426 L162 462 L114 466 Z M290 430 L240 426 L238 462 L286 466 Z" fill="none" stroke="#7d9dbd" strokeWidth="1.2" strokeDasharray="3 2" />
        <path d="M108 392 C118 420 120 450 116 480 M292 392 C282 420 280 450 284 480" stroke="#86a6c6" strokeWidth="1.2" fill="none" />
      </g>

      {/* head (sway, nods, tilt) */}
      <g ref={set("head")}>
        {/* hair behind the head: long waves over the shoulders */}
        <path fill="url(#av-hair-dark)" d="M200 96 C128 96 96 150 98 222 C99 270 92 300 84 334 C76 368 92 386 82 414 C74 438 92 458 118 452 C108 430 122 412 116 390 C110 366 130 350 128 320 L272 320 C270 350 290 366 284 390 C278 412 292 430 282 452 C308 458 326 438 318 414 C308 386 324 368 316 334 C308 300 301 270 302 222 C304 150 272 96 200 96 Z" />
        <ellipse cx="116" cy="236" rx="10" ry="18" fill="#efbfa3" />
        <ellipse cx="284" cy="236" rx="10" ry="18" fill="#efbfa3" />
        <circle cx="117" cy="256" r="2.6" fill="#f5f5f5" /><circle cx="283" cy="256" r="2.6" fill="#f5f5f5" />
        <path ref={set("face")} d={face(0)} fill="url(#av-skin)" />
        <g ref={set("chin")}><path d="M186 334 C194 338 206 338 214 334" stroke="#dca386" strokeWidth="1.2" fill="none" opacity="0.6" /></g>
        <g ref={set("cheeks")} opacity="0.25">
          <ellipse cx="150" cy="262" rx="17" ry="10" fill="#f0918a" /><ellipse cx="250" cy="262" rx="17" ry="10" fill="#f0918a" />
        </g>

        {/* eyes */}
        {[["L", EYE_L, 166], ["R", EYE_R, 234]].map(([s, d, cx]) => (
          <g key={s}>
            <g clipPath={`url(#av-eye${s})`}>
              <path d={d} fill="#fbfbfb" />
              <g ref={set(`iris${s}`)}>
                <circle cx={cx} cy="221" r="9" fill="url(#av-iris)" />
                <circle cx={cx} cy="221" r="9" fill="none" stroke="#2c4660" strokeWidth="1" opacity="0.7" />
                <circle cx={cx} cy="221" r="3.9" fill="#1b2633" />
                <circle cx={cx + 2.8} cy="217.8" r="2.1" fill="#fff" opacity="0.92" />
                <circle cx={cx - 2.5} cy="224" r="0.9" fill="#fff" opacity="0.6" />
              </g>
              <rect x={cx - 24} y="208" width="48" height="4" fill="#000" opacity="0.08" />
              <rect ref={set(`lid${s}`)} x={cx - 24} y="208" width="48" height="2" fill="#efc2a6" />
            </g>
            <g ref={set(`lash${s}`)}>
              <path d={s === "L" ? "M145 223 C152 208.5 180 208.5 187 222 M145.5 222.5 L142.5 220.5" : "M213 222 C220 208.5 248 208.5 255 223 M254.5 222.5 L257.5 220.5"} stroke="#3a2a20" strokeWidth="2.4" fill="none" strokeLinecap="round" />
            </g>
            <path d={s === "L" ? "M149 206 C158 200 177 200 185 207" : "M215 207 C223 200 242 200 251 206"} stroke="#d99f84" strokeWidth="1.3" fill="none" opacity="0.75" />
            <path d={s === "L" ? "M150 229 C158 233 175 233 183 228" : "M217 228 C225 233 242 233 250 229"} stroke="#e3ab90" strokeWidth="1" fill="none" opacity="0.6" />
          </g>
        ))}
        <path ref={set("browL")} d="M143 199 C150 190 170 187 186 194 C172 191 154 193 143 199 Z" fill={pal.brow} stroke={pal.brow} strokeWidth="2.4" strokeLinejoin="round" />
        <path ref={set("browR")} d="M214 194 C230 187 250 190 257 199 C246 193 228 191 214 194 Z" fill={pal.brow} stroke={pal.brow} strokeWidth="2.4" strokeLinejoin="round" />

        {/* soft face shading */}
        <path d="M128 280 C140 312 168 336 200 340 C232 336 260 312 272 280 C262 318 236 344 200 346 C164 344 138 318 128 280 Z" fill="#d99c80" opacity="0.25" />
        {/* nose: soft side shadow and tip only */}
        <path d="M207 244 C209 252 210 258 210.5 263" stroke="#e3ad92" strokeWidth="5" fill="none" strokeLinecap="round" opacity="0.22" />
        <path d="M191 268 C195 274 205 274 209 268" stroke="#cf9175" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        <ellipse cx="195" cy="270" rx="2.2" ry="1.2" fill="#c08068" opacity="0.55" /><ellipse cx="205" cy="270" rx="2.2" ry="1.2" fill="#c08068" opacity="0.55" />
        <ellipse cx="200" cy="262" rx="4" ry="3" fill="#fff" opacity="0.18" />

        {/* mouth: inner cavity, teeth, tongue, lips */}
        <path ref={set("inner")} d="" fill="#5a2430" />
        <g clipPath="url(#av-mouth)">
          <rect ref={set("teeth")} x="0" y="0" width="0" height="0" rx="2" fill="#f7f4ef" />
          <ellipse ref={set("tongue")} cx="200" cy="304" rx="0" ry="0" fill="#c95b6a" />
        </g>
        <path ref={set("upper")} d="" fill="#c9666d" />
        <path ref={set("lower")} d="" fill="#d97c80" />
        <ellipse cx="203" cy="314" rx="7" ry="1.6" fill="#fff" opacity="0.22" />

        {/* hair in front: side part and face-framing waves */}
        <path fill="url(#av-hair)" d="M222 100 C170 98 128 124 116 176 C110 204 112 236 118 258 C122 232 130 204 142 182 C156 156 184 140 214 132 C200 150 196 168 198 176 C214 152 240 138 262 140 C276 156 284 186 284 214 C286 236 284 252 282 262 C296 232 300 196 292 166 C282 126 256 102 222 100 Z" />
        <path fill="url(#av-hair)" d="M118 250 C110 290 120 318 110 350 C100 382 118 404 104 430 C122 424 132 400 128 376 C124 350 138 330 132 300 C128 280 124 264 118 250 Z" />
        <path fill="url(#av-hair)" d="M282 252 C292 290 280 318 290 350 C300 382 282 404 296 430 C278 424 268 400 272 376 C276 350 262 330 268 300 C272 280 276 264 282 252 Z" />
        <path d="M150 140 C170 128 196 124 214 132 M240 120 C258 126 276 144 284 170" stroke="#fff4cf" strokeWidth="2" fill="none" opacity="0.6" />
        {/* strand texture so the hair doesn't read as one flat shape */}
        <g stroke="#c9a15e" strokeWidth="1.1" fill="none" opacity="0.55" strokeLinecap="round">
          <path d="M218 104 C190 108 156 126 136 160 M226 106 C206 116 186 132 170 152 M232 108 C252 116 272 140 280 176" />
          <path d="M196 112 C170 120 146 142 130 180 M244 112 C262 124 278 150 284 196 M210 128 C222 120 242 120 256 132" />
          <path d="M122 270 C118 300 124 330 116 362 M126 300 C130 330 120 360 116 400 M278 270 C282 300 276 330 284 362 M274 300 C270 330 280 360 284 400" />
        </g>
        <g stroke="#fff1c4" strokeWidth="1" fill="none" opacity="0.5" strokeLinecap="round">
          <path d="M204 110 C180 116 158 132 144 156 M238 110 C256 118 270 136 278 160 M120 290 C116 320 122 345 114 375 M280 290 C284 320 278 345 286 375" />
        </g>
      </g>
    </svg>
  );
}
