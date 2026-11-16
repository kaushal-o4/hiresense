// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/voice/RoomSidePanels.jsx
//
// FILE PURPOSE:
// Right-hand panels of the live interview room: progress, running transcript and private notes.
//
// WHAT THIS FILE DOES:
// 1. Shows question number, total and elapsed time.
// 2. Shows the transcript of the conversation.
// 3. Private notes area.
//
// HOW THIS FILE WORKS:
// Presentational component fed by LiveVoiceInterview.jsx.
//
// IMPORTANT FUNCTIONS:
//    Other helper functions: RoomSidePanels
//
// INPUT:
// Props: session, question number, timer, etc.
//
// OUTPUT:
// Side panels UI.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: voice/RoomParts.jsx, voice/roomUtils.js
//    Used by: pages/student/LiveVoiceInterview.jsx
//
// IMPORTANT DEPENDENCIES:
//    react-router-dom
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* Right-hand panels of the live interview room: progress, how-it-works tips, running transcript and private notes. */
import { Link } from "react-router-dom";
import { Keyboard, Mic, PenLine, Volume2 } from "lucide-react";
import { Panel, QuestionStepper, Stat, categoryLabel } from "./RoomParts";
import { fmtClock } from "./roomUtils";

const TIPS = [
  { icon: Volume2, text: "Listen to the full question. Use Repeat if you missed it." },
  { icon: Mic, text: "Press the microphone and answer out loud. It stops after a short pause." },
  { icon: PenLine, text: "Check the transcript, fix any mistakes, then submit." },
  { icon: Keyboard, text: "Prefer typing? Choose Type instead at any time." },
];

export default function RoomSidePanels({ id, session, interviewerName, qNumber, total, elapsed, reviewingDraft, hasCurrent,
  notes, setNotes }) {
  const answered = session.questions.filter((q) => q.answer);
  return (
    <>
      <Panel title="Progress">
        <QuestionStepper total={total} answered={session.answered || 0} current={qNumber} />
        <div className="mt-3 grid grid-cols-3 gap-2 text-center">
          <Stat label="Question" value={`${Math.min(qNumber, total)}/${total}`} />
          <Stat label="Answered" value={session.answered || 0} />
          <Stat label="Duration" value={fmtClock(elapsed)} />
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 border-t border-slate-100 pt-3 text-xs">
          <dt className="text-slate-500">Role</dt><dd className="truncate text-right font-medium text-slate-800">{session.job_role}</dd>
          <dt className="text-slate-500">Category</dt><dd className="truncate text-right font-medium text-slate-800">{categoryLabel(session.category)}</dd>
          {session.difficulty && <><dt className="text-slate-500">Difficulty</dt><dd className="truncate text-right font-medium capitalize text-slate-800">{session.difficulty}</dd></>}
        </dl>
      </Panel>
      <Panel title="How it works">
        <ul className="space-y-2.5 text-[13px] text-slate-600">
          {TIPS.map(({ icon: Icon, text }) => (
            <li key={text} className="flex gap-2.5"><Icon size={14} className="mt-0.5 shrink-0 text-slate-400" aria-hidden />{text}</li>
          ))}
        </ul>
      </Panel>
      <Panel title="Transcript">
        <ol className="max-h-72 space-y-3 overflow-y-auto pr-1 text-sm" aria-live="polite">
          {session.questions.map((q) => (
            <li key={q.id}>
              <p className="text-xs font-semibold text-slate-900">{interviewerName} <span className="font-normal text-slate-400">· Q{q.position}{q.is_followup ? " · follow-up" : ""}</span></p>
              <p className="text-slate-700">{q.text}</p>
              {q.answer
                ? <p className="mt-1.5 rounded-lg bg-slate-50 px-2.5 py-1.5 text-slate-600 ring-1 ring-inset ring-slate-200/70"><span className="text-xs font-semibold text-slate-500">You: </span>{q.answer.text}</p>
                : reviewingDraft && <p className="mt-1.5 rounded-lg border border-dashed border-slate-300 px-2.5 py-1.5 italic text-slate-500">{reviewingDraft}</p>}
            </li>
          ))}
          {!answered.length && !hasCurrent && <li className="text-slate-400">The conversation will appear here.</li>}
        </ol>
      </Panel>
      <Panel title="My notes (private)">
        <textarea className="input text-sm" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={4000}
          placeholder="Jot down points to remember. Notes stay in this browser and are never sent or scored." aria-label="Interview notes" />
      </Panel>
      <Link to={`/student/interviews/${id}`} className="block text-center text-xs text-slate-500 hover:text-slate-800 hover:underline">Switch to text view</Link>
    </>
  );
}
