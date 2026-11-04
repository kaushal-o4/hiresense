/* The round-button toolbar of the live interview room (mic, repeat, pause, voice, self-view, settings, end). */
import { Camera, CameraOff, Mic, MicOff, Pause, PhoneOff, Play, Settings2, Volume2, VolumeX } from "lucide-react";
import { ConfirmButton } from "../components/ui";
import { S } from "./interviewMachine";
import { RoundButton } from "./RoomParts";

export default function ControlBar({ st, sttEnabled, toggleMic, replay, resume, pause, voiceOn, toggleVoice, monitoredCamera,
  camHidden, toggleCamera, showSettings, setShowSettings, answered, endInterview }) {
  return (
    <div className="mx-auto flex w-fit max-w-full flex-wrap items-center justify-center gap-2 rounded-full border border-snow/10 bg-night-800/90 p-2 shadow-pop backdrop-blur-xl" role="toolbar" aria-label="Interview controls">
      <RoundButton label={st.recording ? "Stop recording (I'm done)" : "Turn microphone on"} active={st.recording} danger={st.recording}
        disabled={!st.recording && !(st.status === S.LISTENING && sttEnabled)} onClick={toggleMic}>
        {st.recording ? <MicOff size={18} /> : <Mic size={18} />}
      </RoundButton>
      <RoundButton label="Repeat question" disabled={![S.LISTENING, S.REVIEWING].includes(st.status)} onClick={replay}><Volume2 size={18} /></RoundButton>
      {st.status === S.PAUSED
        ? <RoundButton label="Resume" onClick={resume}><Play size={18} /></RoundButton>
        : <RoundButton label="Pause" disabled={![S.PREPARING_SPEECH, S.SPEAKING, S.LISTENING, S.REVIEWING].includes(st.status)} onClick={() => pause()}><Pause size={18} /></RoundButton>}
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
      <ConfirmButton size="sm" variant="danger" className="ml-1 rounded-full"
        message={answered ? "End the interview now and get feedback on the answers so far?" : "End this interview? No answers have been given, so it will be discarded."}
        onConfirm={endInterview}><PhoneOff size={14} /> End</ConfirmButton>
    </div>
  );
}
