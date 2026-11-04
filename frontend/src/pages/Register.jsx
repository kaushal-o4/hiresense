/*
 * Self-registration for students and recruiters (POST /auth/register/{role}). Recruiter accounts stay
 * pending until an admin approves them.
 */

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { post } from "../api";
import { useAuth } from "../auth";
import { Button, ErrorBox, Field, Notice, Tabs } from "../components/ui";
import AuthShell from "./AuthShell";
import { usePrivacyInfo } from "../components/AIConsent";

export default function Register() {
  const { refresh } = useAuth();
  const privacy = usePrivacyInfo();
  const navigate = useNavigate();
  const [role, setRole] = useState("student");
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm: "", college: "", branch: "",
    graduation_year: "", company_name: "", designation: "", company_website: "", industry: "", share: false, aiConsent: false });
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    if (form.password !== form.confirm) return setError("Passwords do not match");
    setBusy(true);
    try {
      const base = { full_name: form.full_name.trim(), email: form.email.trim(), password: form.password };
      const body = role === "student"
        ? { ...base, college: form.college || null, branch: form.branch || null,
            graduation_year: form.graduation_year ? Number(form.graduation_year) : null, share_with_recruiters: form.share,
            ai_consent: !!(privacy?.consent_required && form.aiConsent) }
        : { ...base, company_name: form.company_name, designation: form.designation || null,
            company_website: form.company_website || null, industry: form.industry || null };
      const res = await post(`/auth/register/${role}`, body);
      if (res.pending_approval) {
        setPending(res.message);
      } else {
        const user = await refresh();
        navigate(`/${user.role}`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (pending) {
    return (
      <AuthShell title="Registration received">
        <Notice tone="blue">{pending}</Notice>
        <Link to="/login" className="mt-6 inline-block text-sm font-medium text-brand-600 hover:underline">Back to sign in</Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Create your account" subtitle="Join HireSense as a student or a recruiter.">
      <Tabs value={role} onChange={setRole} tabs={[{ value: "student", label: "I'm a student" }, { value: "recruiter", label: "I'm a recruiter" }]} />
      <form onSubmit={submit} className="space-y-4">
        <ErrorBox message={error} />
        <Field label="Full name"><input className="input" required minLength={2} value={form.full_name} onChange={set("full_name")} /></Field>
        <Field label={role === "recruiter" ? "Work email" : "Email"}>
          <input className="input" type="email" required value={form.email} onChange={set("email")} />
        </Field>
        {role === "student" ? (
          <>
            <Field label="College"><input className="input" value={form.college} onChange={set("college")} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Branch"><input className="input" placeholder="Computer Science" value={form.branch} onChange={set("branch")} /></Field>
              <Field label="Graduation year">
                <input className="input" type="number" min="1990" max="2100" value={form.graduation_year} onChange={set("graduation_year")} />
              </Field>
            </div>
          </>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Company name"><input className="input" required value={form.company_name} onChange={set("company_name")} /></Field>
              <Field label="Industry"><input className="input" value={form.industry} onChange={set("industry")} /></Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Designation"><input className="input" value={form.designation} onChange={set("designation")} /></Field>
              <Field label="Company website"><input className="input" value={form.company_website} onChange={set("company_website")} /></Field>
            </div>
          </>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Password" hint="8+ characters, letters and numbers">
            <input className="input" type="password" required autoComplete="new-password" value={form.password} onChange={set("password")} />
          </Field>
          <Field label="Confirm password">
            <input className="input" type="password" required autoComplete="new-password" value={form.confirm} onChange={set("confirm")} />
          </Field>
        </div>
        {role === "recruiter" && <p className="text-xs text-slate-500">Recruiter accounts are activated after approval by the placement office.</p>}
        {role === "student" && (
          <label className="flex items-start gap-2 text-sm text-slate-600">
            <input type="checkbox" className="mt-1" checked={form.share} onChange={(e) => setForm({ ...form, share: e.target.checked })} />
            <span>Share my profile with recruiters on HireSense (you can change this anytime in Settings).</span>
          </label>
        )}
        {role === "student" && privacy?.consent_required && (
          <label className="flex items-start gap-2 text-sm text-slate-600">
            <input type="checkbox" className="mt-1" checked={form.aiConsent} onChange={(e) => setForm({ ...form, aiConsent: e.target.checked })} />
            <span>I agree that my resume, interview answers{privacy.speech_to_google ? ", voice recordings" : ""} and English practice
              messages are processed by Google Gemini to power the AI features (<Link className="text-brand-600 hover:underline" to="/privacy">privacy notice</Link>).
              Optional now - you will be asked again before your first AI feature.</span>
          </label>
        )}
        <Button type="submit" size="lg" className="w-full" loading={busy}>Create account</Button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-600">
        Already registered? <Link className="font-medium text-brand-600 hover:underline" to="/login">Sign in</Link>
      </p>
    </AuthShell>
  );
}
