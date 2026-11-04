/*
 * Account settings for every role: speech language and voice preferences, privacy, change password
 * and delete account (/settings, /auth/change-password, DELETE /auth/me).
 */

import { useState } from "react";
import { Volume2 } from "lucide-react";
import { api, get, post, put } from "../api";
import { useAuth } from "../auth";
import { Button, Card, ErrorBox, Field, PageHeader, Spinner, useApi, useToast } from "../components/ui";
import { speak } from "../components/useSpeech";
import { usePrivacyInfo } from "../components/AIConsent";

const LANGS = [
  { value: "en-IN", label: "English (India)" }, { value: "en-US", label: "English (US)" },
  { value: "en-GB", label: "English (UK)" }, { value: "en-AU", label: "English (Australia)" },
];

function Toggle({ checked, onChange, label }) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${checked ? "bg-brand-500" : "bg-slate-300"}`}>
      <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-snow shadow transition ${checked ? "left-5" : "left-0.5"}`} />
    </button>
  );
}

export default function Settings() {
  const { user, refresh } = useAuth();
  const toast = useToast();
  const { data, setData, error, loading, reload } = useApi(() => get("/settings"));
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const [pwBusy, setPwBusy] = useState(false);

  const save = async (patch, msg = "Settings saved") => {
    try {
      setData(await put("/settings", patch));
      await refresh();
      toast(msg);
    } catch (e) {
      toast(e.message, "error");
    }
  };

  const changePassword = async (e) => {
    e.preventDefault();
    if (pw.new_password !== pw.confirm) return toast("New passwords do not match", "error");
    setPwBusy(true);
    try {
      await post("/auth/change-password", { current_password: pw.current_password, new_password: pw.new_password });
      toast("Password updated");
      setPw({ current_password: "", new_password: "", confirm: "" });
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setPwBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Account settings" subtitle={user.email} />
      {loading && <Spinner />}
      <ErrorBox message={error} onRetry={reload} />
      {data && (
        <>
          <Card title="Language & voice">
            <div className="grid max-w-2xl gap-5 sm:grid-cols-2">
              <Field label="Speech language" hint="Used for voice interviews, English practice and read-aloud">
                <select className="input" value={data.speech_lang} onChange={(e) => save({ speech_lang: e.target.value })}>
                  {LANGS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
                </select>
              </Field>
              <Field label={`Read-aloud speed (${data.speech_rate}x)`}>
                <div className="flex items-center gap-2">
                  <input type="range" min="0.6" max="1.4" step="0.1" className="flex-1" value={data.speech_rate}
                    onChange={(e) => setData({ ...data, speech_rate: Number(e.target.value) })}
                    onMouseUp={(e) => save({ speech_rate: Number(e.target.value) })}
                    onTouchEnd={(e) => save({ speech_rate: Number(e.target.value) })} aria-label="Speech speed" />
                  <Button size="sm" variant="secondary" onClick={() => speak("This is how the interviewer will sound.", data.speech_lang, data.speech_rate)}>
                    <Volume2 size={14} /> Test
                  </Button>
                </div>
              </Field>
              <div className="flex items-center justify-between gap-4 sm:col-span-2">
                <div><p className="text-sm font-medium">Show subtitles</p><p className="text-xs text-slate-500">Display captions while questions and replies are read aloud.</p></div>
                <Toggle checked={data.subtitles} label="Show subtitles" onChange={(v) => save({ subtitles: v })} />
              </div>
            </div>
          </Card>
          {user.role === "student" && (
            <Card title="Privacy">
              <div className="flex max-w-2xl items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium">Share my profile with recruiters</p>
                  <p className="text-xs text-slate-500">When on, recruiters can find you in the student database and see your skills and summary scores.
                    Detailed interview reports and your resume are only shared with recruiters whose jobs you apply to.</p>
                </div>
                <Toggle checked={data.share_with_recruiters} label="Share profile with recruiters"
                  onChange={(v) => save({ share_with_recruiters: v }, v ? "Your profile is now visible to recruiters" : "Your profile is hidden from recruiter search")} />
              </div>
              <AIConsentSetting />
            </Card>
          )}
        </>
      )}
      <Card title="Change password">
        <form onSubmit={changePassword} className="grid max-w-2xl gap-4 sm:grid-cols-3">
          <Field label="Current password"><input className="input" type="password" required autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
          <Field label="New password"><input className="input" type="password" required autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
          <Field label="Confirm new password"><input className="input" type="password" required autoComplete="new-password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} /></Field>
          <div><Button type="submit" variant="secondary" loading={pwBusy}>Update password</Button></div>
        </form>
      </Card>
      {user.role === "student" && <DeleteAccount />}
    </div>
  );
}

function AIConsentSetting() {
  const { user, setUser } = useAuth();
  const info = usePrivacyInfo();
  const toast = useToast();
  if (!info?.consent_required) return null;
  const agreed = !!user.ai_data_consent_at;
  const change = async (accept) => {
    try {
      const res = await post("/auth/ai-consent", { accept });
      setUser(res.user);
      toast(accept ? "Thanks - AI features are on" : "Consent withdrawn - AI features are off until you agree again");
    } catch (e) {
      toast(e.message, "error");
    }
  };
  return (
    <div className="mt-5 flex max-w-2xl items-center justify-between gap-4 border-t border-slate-200 pt-5">
      <div>
        <p className="text-sm font-medium">Allow processing by Google Gemini</p>
        <p className="text-xs text-slate-500">Resume analysis, AI interviews and English practice send your text
          {info.speech_to_google ? " and voice recordings" : ""} to Google.
          {agreed ? ` Agreed on ${new Date(user.ai_data_consent_at).toLocaleDateString()}.` : " Not agreed - these features are off."}{" "}
          <a href="/privacy" className="text-brand-600 hover:underline">Privacy notice</a></p>
      </div>
      <Toggle checked={agreed} label="Allow processing by Google Gemini" onChange={change} />
    </div>
  );
}


function DeleteAccount() {
  const { setUser } = useAuth();
  const [form, setForm] = useState({ password: "", confirm: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/auth/me", { method: "DELETE", body: form });
      setUser(null); // signed out; the router sends the visitor to the sign-in page
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <Card title="Delete my account">
      <form onSubmit={submit} className="max-w-2xl space-y-4">
        <p className="text-sm text-slate-600">
          This permanently deletes your account and all your data: resumes, interviews and feedback, English practice,
          assessments, job applications, rewards and mentor notes. <b>It cannot be undone.</b>
        </p>
        <ErrorBox message={error} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Your password">
            <input className="input" type="password" autoComplete="current-password" required value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </Field>
          <Field label='Type "DELETE" to confirm'>
            <input className="input" required value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} />
          </Field>
        </div>
        <Button type="submit" variant="danger" loading={busy} disabled={!form.password || form.confirm !== "DELETE"}>
          Permanently delete my account
        </Button>
      </form>
    </Card>
  );
}
