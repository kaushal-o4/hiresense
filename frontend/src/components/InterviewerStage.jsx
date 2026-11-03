/*
 * A live 3D interviewer used as a hero element (sign-in page, student dashboard): the real Avatar3D in `lite` mode
 * (low-power GPU, 20 fps, no HD model), idle/listening animation only - no audio, nothing recorded. Loads lazily,
 * so the page is usable before three.js arrives; if WebGL is unavailable it quietly shows a static backdrop.
 */

import { Suspense, lazy, useEffect, useState } from "react";

const Avatar3D = lazy(() => import("../voice/Avatar3D"));

const PEOPLE = {
  aria: { model: "/avatars/interviewer.glb", name: "Aria", role: "Friendly interviewer" },
  victor: { model: "/avatars/victor.glb", name: "Victor", role: "Strict technical" },
  marcus: { model: "/avatars/marcus.glb", name: "Marcus", role: "Stress interview" },
  elena: { model: "/avatars/elena.glb", name: "Elena", role: "HR interviewer" },
};

function webglOk() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch { return false; }
}

export default function InterviewerStage({ who = "aria", className = "", mode = "listening", children, caption = true }) {
  const p = PEOPLE[who] || PEOPLE.aria;
  const [failed, setFailed] = useState(false);
  const [canRender, setCanRender] = useState(false);
  // Defer the heavy 3D view until the browser is idle, so the form/page is interactive first.
  useEffect(() => {
    if (!webglOk()) { setFailed(true); return; }
    const id = (window.requestIdleCallback || ((f) => setTimeout(f, 250)))(() => setCanRender(true));
    return () => (window.cancelIdleCallback || clearTimeout)(id);
  }, []);
  return (
    <div className={`isolate overflow-hidden ${/\b(absolute|fixed)\b/.test(className) ? "" : "relative"} ${className}`}>
      {/* backdrop: soft spotlight + floor line, so the figure sits in a space rather than on a flat colour */}
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(60%_55%_at_50%_35%,rgba(255,255,255,0.10),transparent_70%)]" aria-hidden />
      <div className="absolute inset-x-0 bottom-0 -z-10 h-1/3 bg-[linear-gradient(to_top,rgba(0,0,0,0.35),transparent)]" aria-hidden />
      {!failed && canRender && (
        // Avatar3D's root is position:relative, so it is sized by this absolutely positioned wrapper.
        <div className="absolute inset-0 animate-fade-up">
          <Suspense fallback={null}>
            <Avatar3D lite testHook={false} mode={mode} interviewer={who} modelUrl={p.model} label={`${p.name}, ${p.role}`}
              onFailed={() => setFailed(true)} className="h-full w-full" />
          </Suspense>
        </div>
      )}
      {caption && (
        <div className="absolute left-3 top-3 inline-flex items-center gap-2 rounded-full border border-snow/10 bg-black/40 px-2.5 py-1 text-[11px] text-snow backdrop-blur-md">
          <span className="relative flex h-1.5 w-1.5"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" /><span className="relative h-1.5 w-1.5 rounded-full bg-emerald-400" /></span>
          <span className="font-medium">{p.name}</span><span className="text-snow/60">· {p.role}</span>
        </div>
      )}
      {children}
    </div>
  );
}
