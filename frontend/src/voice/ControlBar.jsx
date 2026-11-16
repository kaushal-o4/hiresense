// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/voice/ControlBar.jsx
//
// FILE PURPOSE:
// The round-button toolbar of the live interview (mic, repeat, pause, voice, self-view, settings,
// end).
//
// WHAT THIS FILE DOES:
// 1. Shows buttons enabled or disabled according to the interview state.
// 2. Calls the page's callbacks when pressed.
//
// HOW THIS FILE WORKS:
// Uses interviewMachine state values to decide which buttons are active.
//
// IMPORTANT FUNCTIONS:
//    Other helper functions: ControlBar
//
// INPUT:
// Props: interview state and callback functions.
//
// OUTPUT:
// Toolbar UI.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: components/SharedUiComponents.jsx, voice/RoomParts.jsx, voice/interviewMachine.js
//    Used by: pages/student/LiveVoiceInterview.jsx
//
// IMPORTANT DEPENDENCIES:
//    lucide-react
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* The control dock of the live interview room (mic, repeat, pause, voice, self-view, settings, end). */
import { Camera, CameraOff, Mic, MicOff, Pause, PhoneOff, Play, Settings2, Volume2, VolumeX } from "lucide-react";
import { ConfirmButton } from "../components/SharedUiComponents";
import { S } from "./interviewMachine";
import { RoundButton } from "./RoomParts";

export default function ControlBar({ st, sttEnabled, toggleMic, replay, resume, pause, voiceOn, toggleVoice, monitoredCamera,
  camHidden, toggleCamera, showSettings, setShowSettings, answered, endInterview }) {
  const micReady = st.status === S.LISTENING && sttEnabled;
  return (
    <div className="flex w-full flex-wrap items-center justify-center gap-2 sm:gap-3" role="toolbar" aria-label="Interview controls">
      <div className="flex items-center gap-2">
        <RoundButton label="Repeat question" disabled={![S.LISTENING, S.REVIEWING].includes(st.status)} onClick={replay}><Volume2 size={18} /></RoundButton>
        {st.status === S.PAUSED
          ? <RoundButton label="Resume" onClick={resume}><Play size={18} /></RoundButton>
          : <RoundButton label="Pause" disabled={![S.PREPARING_SPEECH, S.SPEAKING, S.LISTENING, S.REVIEWING].includes(st.status)} onClick={() => pause()}><Pause size={18} /></RoundButton>}
      </div>
      {/* the microphone is the primary action: larger, and the only light button on the dark dock */}
      <span className="relative">
        {micReady && !st.recording && <span className="pointer-events-none absolute inset-0 rounded-full bg-snow/30 animate-pulse-ring" aria-hidden />}
        <RoundButton primary label={st.recording ? "Stop recording (I'm done)" : "Turn microphone on"} danger={st.recording} active={st.recording}
          disabled={!st.recording && !micReady} onClick={toggleMic}>
          {st.recording ? <MicOff size={22} /> : <Mic size={22} />}
        </RoundButton>
      </span>
      <div className="flex items-center gap-2">
        <RoundButton label={voiceOn ? "Turn interviewer voice off" : "Turn interviewer voice on"} onClick={toggleVoice}>
          {voiceOn ? <Volume2 size={18} /> : <VolumeX size={18} />}
        </RoundButton>
        {/* The camera runs only when the candidate opted into monitoring at setup; this hides/shows the self-view. */}
        {monitoredCamera && (
          <RoundButton label={camHidden ? "Show my self-view (camera stays on for monitoring)" : "Hide my self-view (camera stays on for monitoring - use Stop monitoring to turn it off)"} onClick={toggleCamera}>
            {camHidden ? <Camera size={18} /> : <CameraOff size={18} />}
          </RoundButton>
        )}
        <RoundButton label="Settings" active={showSettings} onClick={() => setShowSettings((v) => !v)}><Settings2 size={18} /></RoundButton>
      </div>
      <span className="mx-1 hidden h-7 w-px bg-snow/10 sm:block" aria-hidden />
      <ConfirmButton size="md" variant="danger" className="!h-11 rounded-full px-5"
        message={answered ? "End the interview now and get feedback on the answers so far?" : "End this interview? No answers have been given, so it will be discarded."}
        onConfirm={endInterview}><PhoneOff size={15} /> End</ConfirmButton>
    </div>
  );
}
