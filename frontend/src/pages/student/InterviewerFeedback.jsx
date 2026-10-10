import { Suspense, lazy, useCallback, useEffect, useRef, useState } from "react";
import { Square, Volume2 } from "lucide-react";
import { get, post } from "../../api";
import { Button } from "../../components/ui";
import { SpeechPlayer } from "../../voice/speechPlayer";
import { browserVoiceOpts, speakBody } from "../../voice/useInterviewers";

const Avatar3D = lazy(() => import("../../voice/Avatar3D"));

/**
 * End of the interview: the interviewer delivers their closing remarks (written by the AI in the interviewer's
 * style, from the actual answers) aloud, in the FEEDBACK avatar state, with lip sync. Nothing plays automatically.
 */
export default function InterviewerFeedback({ session, persona, voice: voiceProp, rate = 1 }) {
  const remarks = session.report?.closing_remarks;
  const [voice, setVoice] = useState(voiceProp ?? null);
  const [speaking, setSpeaking] = useState(false);
  const [busy, setBusy] = useState(false);
  const player = useRef(null);
  if (!player.current) player.current = new SpeechPlayer();
  const getVisemes = useCallback(() => player.current.getVisemes(), []);
  useEffect(() => { if (voiceProp === undefined) get("/voice/status").then(setVoice).catch(() => setVoice({})); }, [voiceProp]);
  useEffect(() => () => player.current?.close(), []);

  const play = async () => {
    if (speaking) { player.current.stop(); setSpeaking(false); return; }
    player.current.unlock();
    setBusy(true);
    try {
      let playing = null;
      if (voice?.tts?.enabled) {
        try { playing = player.current.play(await post("/voice/speak", speakBody(persona, remarks, rate))); } catch { /* browser voice */ }
      }
      setBusy(false);
      setSpeaking(true);
      await (playing || player.current.playBrowser(remarks, browserVoiceOpts(persona, rate)));
    } catch { /* playback failed: the text is on screen */ } finally {
      setBusy(false);
      setSpeaking(false);
    }
  };

  return (
    <div className="grid overflow-hidden rounded-2xl border border-slate-200 bg-white md:grid-cols-[280px_1fr]">
      <Suspense fallback={<div className="h-56 bg-slate-200" />}>
        <Avatar3D getVisemes={getVisemes} mode={speaking ? "feedback" : "idle"} interviewer={persona.id} modelUrl={persona.ui.model}
          hdModelUrl={persona.ui.hd_model} label={`${persona.name}, giving feedback`} className="h-56 w-full md:h-full md:min-h-[14rem]" />
      </Suspense>
      <div className="flex flex-col gap-3 p-5">
        <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: persona.ui.accent }}>{persona.name} · {persona.title}</p>
        {remarks ? (
          <>
            <blockquote className="border-l-4 pl-3 text-slate-700" style={{ borderColor: persona.ui.accent }}>{remarks}</blockquote>
            <div><Button variant="secondary" loading={busy} onClick={play}>{speaking ? <><Square size={14} /> Stop</> : <><Volume2 size={14} /> Hear {persona.name}'s feedback</>}</Button></div>
          </>
        ) : (
          <p className="text-sm text-slate-500">{persona.name}'s spoken feedback appears once the AI has written your report.</p>
        )}
        <p className="text-xs text-slate-400">The scores below are calculated the same way whichever interviewer you choose.</p>
      </div>
    </div>
  );
}
