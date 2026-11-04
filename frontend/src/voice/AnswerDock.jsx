/* The answer area under the interviewer: microphone level and live caption, typed answer, transcript review. */
import { Keyboard, Mic, RotateCcw, Send } from "lucide-react";
import { Button, Spinner } from "../components/ui";
import { S } from "./interviewMachine";

export default function AnswerDock({ st, dispatch, inputMode, setInputMode, micLevel, eosMs, typeInstead, appendTo, partial,
  sttEnabled, draft, setDraft, submit, stage, interviewerName }) {
  return (
    <div className="card p-4">
      {st.status === S.LISTENING && inputMode === "voice" && (
        <div className="flex flex-wrap items-center gap-3">
          <div className="h-1.5 w-40 overflow-hidden rounded-full bg-slate-200" role="meter" aria-label="Microphone level" aria-valuenow={Math.round(micLevel * 900)} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 shadow-[0_0_10px_rgb(16_185_129/0.7)] transition-[width] duration-75" style={{ width: `${Math.min(100, micLevel * 900)}%` }} />
          </div>
          <span className="text-xs text-slate-500">{st.recording
            ? `Recording - it stops after a ${(eosMs / 1000).toFixed(1)} s pause (change in Settings), or press the microphone button when you're done.`
            : "Microphone is off. Press the microphone button to answer."}</span>
          <Button size="sm" variant="ghost" className="ml-auto" onClick={typeInstead}><Keyboard size={14} /> Type instead</Button>
          {st.recording && (appendTo.current || partial) && (
            <p className="w-full rounded-lg border border-slate-200 bg-slate-100/50 px-3 py-2 text-sm italic text-slate-700" aria-live="polite">
              <span className="text-xs font-semibold not-italic text-slate-500">Heard so far: </span>{[appendTo.current, partial].filter(Boolean).join(" ")}
            </p>
          )}
        </div>
      )}
      {st.status === S.LISTENING && inputMode === "text" && (
        <div className="flex items-center gap-3">
          <Button onClick={() => dispatch({ type: "TYPE_INSTEAD" })}><Keyboard size={16} /> Write my answer</Button>
          {sttEnabled && <Button variant="ghost" onClick={() => setInputMode("voice")}><Mic size={14} /> Use microphone</Button>}
        </div>
      )}
      {st.status === S.TRANSCRIBING && <Spinner label={partial ? "Finishing the transcript…" : "Transcribing your answer locally…"} />}
      {st.status === S.REVIEWING && (
        <div>
          <label className="label" htmlFor="answer">{inputMode === "voice" ? "Your answer (transcribed - correct any mistakes)" : "Your answer"}</label>
          <textarea id="answer" className="input" rows={5} maxLength={8000} value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button onClick={submit} disabled={!draft.trim()}><Send size={16} /> Submit answer</Button>
            {sttEnabled && draft.trim() && <Button variant="secondary" onClick={() => { appendTo.current = draft.trim(); setInputMode("voice"); dispatch({ type: "RERECORD" }); }}><Mic size={14} /> Continue speaking</Button>}
            {sttEnabled && <Button variant="ghost" onClick={() => { appendTo.current = ""; setInputMode("voice"); setDraft(""); dispatch({ type: "RERECORD" }); }}><RotateCcw size={14} /> Record again</Button>}
            <span className="ml-auto text-xs text-slate-500">{draft.trim() ? draft.trim().split(/\s+/).length : 0} words</span>
          </div>
        </div>
      )}
      {st.status === S.EVALUATING && <Spinner label={stage === "question" ? `${interviewerName} is preparing the next question…` : `${interviewerName} is considering your answer…`} />}
    </div>
  );
}
