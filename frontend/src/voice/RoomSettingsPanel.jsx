// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/voice/RoomSettingsPanel.jsx
//
// FILE PURPOSE:
// Settings panel of the live interview room.
//
// WHAT THIS FILE DOES:
// 1. Voice on/off and speed.
// 2. Captions and subtitle size.
// 3. Auto microphone, end-of-speech pause and auto-send.
// 4. 3D graphics quality.
//
// HOW THIS FILE WORKS:
// Calls setSetting/setAvatarQuality passed in by the page.
//
// IMPORTANT FUNCTIONS:
//    Other helper functions: RoomSettingsPanel
//
// INPUT:
// Props: settings and setter functions.
//
// OUTPUT:
// Settings UI.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: voice/RoomParts.jsx, voice/avatarStates.js
//    Used by: pages/student/LiveVoiceInterview.jsx
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* The live interview room's Settings panel (voice, captions, microphone, auto-send, graphics). */
import { AVATAR_QUALITY, saveQuality } from "./avatarStates";
import { Panel, Segmented, Toggle } from "./RoomParts";

export default function RoomSettingsPanel({ settings, setSetting, toggleVoice, eosMs, use3d, avatarQuality, setAvatarQuality }) {
  return (
    <Panel title="Settings">
      <div className="space-y-3 text-sm">
        <Toggle label="Interviewer voice" checked={settings.voiceOn} onChange={toggleVoice} />
        <Toggle label="Subtitles / captions" checked={settings.captions || !settings.voiceOn} disabled={!settings.voiceOn}
          onChange={(v) => setSetting({ captions: v })} hint={!settings.voiceOn ? "Always on while the voice is off." : null} />
        <label className="block">
          <span className="text-slate-600">Speech speed: {settings.rate.toFixed(2)}×</span>
          <input type="range" min="0.75" max="1.3" step="0.05" value={settings.rate} className="w-full"
            onChange={(e) => setSetting({ rate: Number(e.target.value) })} aria-label="Speech speed" />
          <span className="text-xs text-slate-400">Applies from the next question.</span>
        </label>
        <div>
          <span className="text-slate-600">Subtitle size</span>
          <div><Segmented label="Subtitle size" value={settings.subtitleSize} onChange={(z) => setSetting({ subtitleSize: z })}
            options={[["sm", "Small"], ["md", "Medium"], ["lg", "Large"]]} /></div>
        </div>
        <Toggle label="Turn the microphone on automatically" checked={settings.autoMic} onChange={(v) => setSetting({ autoMic: v })} />
        <label className="block">
          <span className="text-slate-600">Stop recording after a pause of {(eosMs / 1000).toFixed(1)} s</span>
          <input type="range" min="600" max="4000" step="100" value={eosMs} className="w-full"
            onChange={(e) => setSetting({ endOfSpeechMs: Number(e.target.value) })} aria-label="Pause that ends an answer (milliseconds)" />
          <span className="text-xs text-slate-400">Raise it if you get cut off while thinking. You can always press "Continue speaking" to add more.
            {settings.endOfSpeechMs && <button type="button" className="ml-1 underline" onClick={() => setSetting({ endOfSpeechMs: null })}>Use the default</button>}</span>
        </label>
        <Toggle label="Send my answer automatically when I stop talking (turn off to check the text first)" checked={settings.autoSend} onChange={(v) => setSetting({ autoSend: v })}
          hint="Off: you can read and correct the text first." />
        {use3d && (
          <div>
            <span className="text-slate-600">Interviewer graphics</span>
            <div><Segmented label="Interviewer graphics" value={avatarQuality} onChange={(q) => { saveQuality(q); setAvatarQuality(q); }}
              options={Object.entries(AVATAR_QUALITY)} /></div>
            <span className="text-xs text-slate-400">Use Performance if the interviewer stutters. Changing it reloads the 3D view.</span>
          </div>
        )}
        <label className="block">
          <span className="text-slate-600">Language</span>
          <select className="input mt-1" value="en" disabled aria-describedby="lang-note"><option value="en">English</option></select>
          <span id="lang-note" className="text-xs text-slate-400">The local speech models (Kokoro voice, Whisper base.en) support English only.</span>
        </label>
      </div>
    </Panel>
  );
}
