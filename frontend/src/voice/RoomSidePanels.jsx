/* Right-hand panels of the live interview room: progress, running transcript and private notes. */
import { Link } from "react-router-dom";
import { Panel, Stat } from "./RoomParts";
import { fmtClock } from "./roomUtils";

export default function RoomSidePanels({ id, session, interviewerName, qNumber, total, elapsed, reviewingDraft, hasCurrent,
  notes, setNotes }) {
  const answered = session.questions.filter((q) => q.answer);
  return (
    <>
      <Panel title="Progress">
        <div className="grid grid-cols-3 gap-2 text-center">
          <Stat label="Question" value={`${Math.min(qNumber, total)}/${total}`} />
          <Stat label="Answered" value={session.answered || 0} />
          <Stat label="Duration" value={fmtClock(elapsed)} />
        </div>
      </Panel>
      <Panel title="Transcript">
        <ol className="max-h-72 space-y-3 overflow-y-auto pr-1 text-sm" aria-live="polite">
          {session.questions.map((q) => (
            <li key={q.id}>
              <p className="text-xs font-semibold text-slate-900">{interviewerName} <span className="font-normal text-slate-400">· Q{q.position}{q.is_followup ? " · follow-up" : ""}</span></p>
              <p className="text-slate-800">{q.text}</p>
              {q.answer
                ? <p className="mt-1 rounded bg-slate-50 px-2 py-1 text-slate-600"><span className="text-xs font-semibold text-slate-500">You: </span>{q.answer.text}</p>
                : reviewingDraft && <p className="mt-1 rounded border border-dashed border-slate-300 px-2 py-1 italic text-slate-500">{reviewingDraft}</p>}
            </li>
          ))}
          {!answered.length && !hasCurrent && <li className="text-slate-400">The conversation will appear here.</li>}
        </ol>
      </Panel>
      <Panel title="My notes (private)">
        <textarea className="input text-sm" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={4000}
          placeholder="Jot down points to remember. Notes stay in this browser and are never sent or scored." aria-label="Interview notes" />
      </Panel>
      <Link to={`/student/interviews/${id}`} className="block text-center text-xs text-slate-500 hover:underline">Switch to text view</Link>
    </>
  );
}
