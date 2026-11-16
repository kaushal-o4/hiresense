// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/ForgotPassword.jsx
//
// FILE PURPOSE:
// Page to request a password-reset link by email.
//
// WHAT THIS FILE DOES:
// 1. Takes the account email.
// 2. Calls POST /auth/forgot-password.
// 3. Always shows the same neutral message.
//
// HOW THIS FILE WORKS:
// A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and
// modal state with useState, sends changes with post/put/patch/del and shows the result with the
// shared components from SharedUiComponents.jsx. API calls used: POST /auth/forgot-password.
//
// IMPORTANT FUNCTIONS:
//    - ForgotPassword()
//        Form component.
//
// INPUT:
// Email address.
//
// OUTPUT:
// Confirmation message.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: apiClient.js, components/SharedUiComponents.jsx, pages/AuthShell.jsx
//    Used by: App.jsx
//
// IMPORTANT DEPENDENCIES:
//    react, react-router-dom
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* Request a password-reset link by email (POST /auth/forgot-password). */

import { useState } from "react";
import { Link } from "react-router-dom";
import { MailCheck } from "lucide-react";
import { post } from "../apiClient";
import { Button, ErrorBox, Field } from "../components/SharedUiComponents";
import AuthShell from "./AuthShell";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);

  const invalid = !email.trim() ? "Enter your email address." : !EMAIL_RE.test(email.trim()) ? "Enter a valid email address." : null;

  const submit = async (e) => {
    e.preventDefault();
    setTouched(true);
    if (invalid) return;
    setBusy(true);
    setError(null);
    try {
      const r = await post("/auth/forgot-password", { email: email.trim() });
      setDone(r.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Forgot your password?" subtitle="Enter your account email and we'll send you a link to choose a new one.">
      {done ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600"><MailCheck size={19} /></span>
          <p className="mt-3 text-sm font-semibold text-slate-900">Check your inbox</p>
          <p className="mt-1 text-sm leading-relaxed text-slate-600" role="status">{done}</p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-5" noValidate>
          <ErrorBox message={error} />
          <Field label="Email" error={touched ? invalid : null}>
            <input className="input h-11" type="email" autoComplete="email" required value={email} autoFocus aria-invalid={!!(touched && invalid)}
              placeholder="you@college.edu" onBlur={() => setTouched(true)} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Button type="submit" size="lg" className="w-full" loading={busy}>Send reset link</Button>
        </form>
      )}
      <p className="mt-8 text-center text-sm text-slate-600">
        Remembered it? <Link className="font-medium text-brand-600 hover:underline" to="/login">Back to sign in</Link>
      </p>
    </AuthShell>
  );
}
