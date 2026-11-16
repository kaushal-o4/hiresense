// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/Register.jsx
//
// FILE PURPOSE:
// Self-registration page for students and recruiters.
//
// WHAT THIS FILE DOES:
// 1. Lets the user choose student or recruiter.
// 2. Collects name, email, password and role-specific details.
// 3. Calls POST /auth/register/{role}.
// 4. Shows the hosted-AI consent notice when the server uses Gemini.
// 5. Recruiters may stay 'pending' until an admin approves them.
//
// HOW THIS FILE WORKS:
// A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and
// modal state with useState, sends changes with post/put/patch/del and shows the result with the
// shared components from SharedUiComponents.jsx. API calls used: POST /auth/register/student, POST
// /auth/register/recruiter.
//
// IMPORTANT FUNCTIONS:
//    - Register()
//        Registration form component.
//
// INPUT:
// Form fields typed by the user.
//
// OUTPUT:
// A new account (and sign-in for students).
//
// FILES CONNECTED TO THIS FILE:
//    Uses: AuthContext.jsx, apiClient.js, components/HostedAiConsentGate.jsx,
//    components/SharedUiComponents.jsx, pages/AuthShell.jsx
//    Used by: App.jsx
//
// IMPORTANT DEPENDENCIES:
//    react, react-router-dom
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/*
 * Self-registration for students and recruiters (POST /auth/register/{role}). Recruiter accounts stay
 * pending until an admin approves them.
 */

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Clock } from "lucide-react";
import { post } from "../apiClient";
import { useAuth } from "../AuthContext";
import { Button, ErrorBox, Field, Tabs, buttonClass } from "../components/SharedUiComponents";
import AuthShell, { PasswordField } from "./AuthShell";
import { usePrivacyInfo } from "../components/HostedAiConsentGate";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validate(form, role) {
  const e = {};
  if (form.full_name.trim().length < 2) e.full_name = "Enter your full name.";
  if (!form.email.trim()) e.email = "Enter your email address.";
  else if (!EMAIL_RE.test(form.email.trim())) e.email = "Enter a valid email address.";
  if (role === "recruiter" && !form.company_name.trim()) e.company_name = "Enter your company name.";
  if (form.password.length < 8 || !/[a-z]/i.test(form.password) || !/\d/.test(form.password)) e.password = "Use 8+ characters with letters and numbers.";
  if (form.confirm && form.password !== form.confirm) e.confirm = "Passwords do not match";
  else if (!form.confirm) e.confirm = "Confirm your password.";
  return e;
}

export default function Register() {
  const { refresh } = useAuth();
  const privacy = usePrivacyInfo();
  const navigate = useNavigate();
  const [role, setRole] = useState("student");
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm: "", college: "", branch: "",
    graduation_year: "", company_name: "", designation: "", company_website: "", industry: "", share: false, aiConsent: false });
  const [touched, setTouched] = useState({});
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const blur = (k) => () => setTouched((t) => ({ ...t, [k]: true }));
  const errs = validate(form, role);
  const err = (k) => (touched[k] ? errs[k] : null);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setTouched({ full_name: true, email: true, company_name: true, password: true, confirm: true });
    if (Object.keys(errs).length) return;
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
    } catch (err2) {
      setError(err2.message);
    } finally {
      setBusy(false);
    }
  };

  if (pending) {
    return (
      <AuthShell title="Registration received" subtitle="Thanks for registering your company on HireSense.">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-600"><Clock size={19} /></span>
          <p className="mt-3 text-sm leading-relaxed text-slate-700" role="status">{pending}</p>
        </div>
        <Link to="/login" className={`${buttonClass("secondary", "lg")} mt-6 w-full`}>Back to sign in</Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Create your account" subtitle="Join HireSense as a student or a recruiter.">
      <Tabs value={role} onChange={setRole} tabs={[{ value: "student", label: "I'm a student" }, { value: "recruiter", label: "I'm a recruiter" }]} />
      <form onSubmit={submit} className="space-y-4" noValidate>
        <ErrorBox message={error} />
        <Field label="Full name" error={err("full_name")}>
          <input className="input" required minLength={2} autoComplete="name" value={form.full_name} onChange={set("full_name")}
            onBlur={blur("full_name")} aria-invalid={!!err("full_name")} />
        </Field>
        <Field label={role === "recruiter" ? "Work email" : "Email"} error={err("email")}>
          <input className="input" type="email" required autoComplete="email" value={form.email} onChange={set("email")}
            onBlur={blur("email")} aria-invalid={!!err("email")} />
        </Field>
        {role === "student" ? (
          <>
            <Field label="College"><input className="input" value={form.college} onChange={set("college")} /></Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Branch"><input className="input" placeholder="Computer Science" value={form.branch} onChange={set("branch")} /></Field>
              <Field label="Graduation year">
                <input className="input" type="number" min="1990" max="2100" value={form.graduation_year} onChange={set("graduation_year")} />
              </Field>
            </div>
          </>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Company name" error={err("company_name")}>
                <input className="input" required value={form.company_name} onChange={set("company_name")} onBlur={blur("company_name")}
                  aria-invalid={!!err("company_name")} />
              </Field>
              <Field label="Industry"><input className="input" value={form.industry} onChange={set("industry")} /></Field>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Designation"><input className="input" value={form.designation} onChange={set("designation")} /></Field>
              <Field label="Company website"><input className="input" value={form.company_website} onChange={set("company_website")} /></Field>
            </div>
          </>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <PasswordField id="reg-password" label="Password" className="" hint="8+ characters, letters and numbers" error={err("password")}
            required autoComplete="new-password" value={form.password} onChange={set("password")} onBlur={blur("password")} />
          <PasswordField id="reg-confirm" label="Confirm password" className="" error={err("confirm")}
            required autoComplete="new-password" value={form.confirm} onChange={set("confirm")} onBlur={blur("confirm")} />
        </div>
        {role === "recruiter" && <p className="text-xs text-slate-500">Recruiter accounts are activated after approval by the placement office.</p>}
        {role === "student" && (
          <label className="flex items-start gap-2.5 text-sm text-slate-600">
            <input type="checkbox" className="mt-1" checked={form.share} onChange={(e) => setForm({ ...form, share: e.target.checked })} />
            <span>Share my profile with recruiters on HireSense (you can change this anytime in Settings).</span>
          </label>
        )}
        {role === "student" && privacy?.consent_required && (
          <label className="flex items-start gap-2.5 text-sm text-slate-600">
            <input type="checkbox" className="mt-1" checked={form.aiConsent} onChange={(e) => setForm({ ...form, aiConsent: e.target.checked })} />
            <span>I agree that my resume, interview answers{privacy.speech_to_google ? ", voice recordings" : ""} and English practice
              messages are processed by Google Gemini to power the AI features (<Link className="text-brand-600 hover:underline" to="/privacy">privacy notice</Link>).
              Optional now - you will be asked again before your first AI feature.</span>
          </label>
        )}
        <Button type="submit" size="lg" className="w-full" loading={busy}>Create account</Button>
      </form>
      <p className="mt-8 border-t border-slate-200 pt-6 text-center text-sm text-slate-600">
        Already registered? <Link className="font-medium text-brand-600 hover:underline" to="/login">Sign in</Link>
      </p>
    </AuthShell>
  );
}
