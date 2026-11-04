/* The live interview room's Settings panel (voice, captions, microphone, auto-send, graphics). */
import { AVATAR_QUALITY, saveQuality } from "./avatarStates";
import { Panel, Toggle } from "./RoomParts";

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
          <div className="mt-1 flex gap-1">
            {["sm", "md", "lg"].map((z) => (
              <button key={z} type="button" onClick={() => setSetting({ subtitleSize: z })} aria-pressed={settings.subtitleSize === z}
                className={`rounded border px-3 py-1 text-xs ${settings.subtitleSize === z ? "border-brand-400/60 bg-brand-500 text-snow shadow-glow" : "border-slate-300"}`}>
                {{ sm: "Small", md: "Medium", lg: "Large" }[z]}
              </button>
            ))}
          </div>
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
            <div className="mt-1 flex flex-wrap gap-1">
              {Object.entries(AVATAR_QUALITY).map(([q, name]) => (
                <button key={q} type="button" onClick={() => { saveQuality(q); setAvatarQuality(q); }} aria-pressed={avatarQuality === q}
                  className={`rounded border px-3 py-1 text-xs ${avatarQuality === q ? "border-brand-400/60 bg-brand-500 text-snow shadow-glow" : "border-slate-300"}`}>
                  {name}
                </button>
              ))}
            </div>
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
