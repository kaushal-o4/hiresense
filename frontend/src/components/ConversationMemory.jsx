// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/components/ConversationMemory.jsx
//
// FILE PURPOSE:
// Shows what Aria (the English practice partner) remembers in the current English conversation.
//
// WHAT THIS FILE DOES:
// 1. Lists earlier topics, the student's interests and important details Aria noted.
// 2. Shows which grammar points are being practised.
// 3. Shows the current learning mode label.
//
// HOW THIS FILE WORKS:
// It receives the memory object returned by the backend and renders it in a Card; renders nothing if
// there is no memory.
//
// IMPORTANT FUNCTIONS:
//    - ConversationMemory()
//        What Aria remembers from this conversation (topics, interests, details), so the
//        student can see it.
//
// IMPORTANT VARIABLES / STATE:
//    - LEARNING_MODE_LABEL
//        Readable names of the three learning modes.
//
// INPUT:
// Props: memory (from the English session API) and learningMode.
//
// OUTPUT:
// A 'What Aria remembers' card.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: components/SharedUiComponents.jsx
//    Used by: pages/student/EnglishAvatarSession.jsx, pages/student/EnglishSession.jsx
//
// IMPORTANT DEPENDENCIES:
//    lucide-react
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* Panel showing what Aria remembers in an English conversation (used by EnglishSession and EnglishAvatarSession). */

import { Brain } from "lucide-react";
import { Card, Pill } from "./SharedUiComponents";

export const LEARNING_MODE_LABEL = {
  free_conversation: "Free conversation",
  english_learning: "English learning",
  confidence: "Confidence building",
};

/** What Aria remembers from this conversation (topics, interests, details), so the student can see it. */
export default function ConversationMemory({ memory, learningMode }) {
  if (!memory) return null;
  const earlier = memory.previous_topics || [];
  const interests = memory.candidate_interests || [];
  const details = memory.important_details || [];
  const practising = memory.practising || [];
  return (
    <Card title="What Aria remembers">
      <div className="space-y-3 text-sm">
        <p className="flex items-center gap-2">
          <Brain size={16} className="shrink-0 text-brand-600" />
          <span>Talking about <b>{memory.current_topic || "anything you like"}</b></span>
        </p>
        {earlier.length > 0 && (
          <div>
            <p className="text-xs text-slate-500">Earlier topics</p>
            <div className="mt-1 flex flex-wrap gap-1">{earlier.map((t) => <Pill key={t}>{t}</Pill>)}</div>
          </div>
        )}
        {interests.length > 0 && (
          <div>
            <p className="text-xs text-slate-500">Your interests</p>
            <div className="mt-1 flex flex-wrap gap-1">{interests.map((t) => <Pill key={t} tone="brand">{t}</Pill>)}</div>
          </div>
        )}
        {details.length > 0 && (
          <ul className="list-disc space-y-0.5 pl-5 text-xs text-slate-600">{details.map((d) => <li key={d}>{d}</li>)}</ul>
        )}
        {practising.length > 0 && <p className="text-xs text-slate-500">Practising: {practising.join(", ")}</p>}
        <p className="text-xs text-slate-400">
          {LEARNING_MODE_LABEL[learningMode] || LEARNING_MODE_LABEL.free_conversation} mode. Change the subject any time: just say
          “Can we talk about … instead?”
        </p>
      </div>
    </Card>
  );
}
