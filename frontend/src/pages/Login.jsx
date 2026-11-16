// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/Login.jsx
//
// FILE PURPOSE:
// The sign-in page for all four roles.
//
// WHAT THIS FILE DOES:
// 1. Shows email and password fields inside AuthShell.
// 2. Calls login() from AuthContext (POST /auth/login sets the session cookie).
// 3. Shows an error message if sign-in fails.
// 4. After login, App.jsx sends the user to their portal home.
//
// HOW THIS FILE WORKS:
// A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and
// modal state with useState, sends changes with post/put/patch/del and shows the result with the
// shared components from SharedUiComponents.jsx. API calls used: POST /auth/login (through
// AuthContext.login).
//
// IMPORTANT FUNCTIONS:
//    - Login()
//        Login form component.
//
// INPUT:
// Email and password typed by the user.
//
// OUTPUT:
// A signed-in session or an error message.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: AuthContext.jsx, components/SharedUiComponents.jsx, pages/AuthShell.jsx
//    Used by: App.jsx
//
// EXECUTION FLOW:
//    User enters email + password
//       |
//       v
//    login() calls POST /auth/login
//       |
//       v
//    Backend sets cookie
//       |
//       v
//    /auth/me loads user
//       |
//       v
//    Redirect to portal
//
// IMPORTANT DEPENDENCIES:
//    react, react-router-dom
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/*
 * Sign-in page. Calls login() from AuthContext.jsx (POST /auth/login sets the session cookie); App.jsx then routes
 * the user to their portal's home page.
 */

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { Button, ErrorBox, Field } from "../components/SharedUiComponents";
import AuthShell, { PasswordField } from "./AuthShell";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Local demo accounts (created by backend/app/seed_initial_data.py). Shown ONLY by the Vite dev server
// (import.meta.env.DEV) - production builds drop this list entirely, so no password ships to a deployed site.
const DEMO_ACCOUNTS = import.meta.env.DEV ? [
  { role: "Student", email: "student@hiresense.app", password: "Student-Local-2026!" },
  { role: "Recruiter", email: "recruiter@hiresense.app", password: "Recruiter-Local-2026!" },
  { role: "Mentor", email: "mentor@hiresense.app", password: "Mentor-Local-2026!" },
  { role: "Admin", email: "admin@hiresense.app", password: "Admin-Local-2026!" },
] : [];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [touched, setTouched] = useState({});
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const errs = {
    email: !form.email.trim() ? "Enter your email address." : !EMAIL_RE.test(form.email.trim()) ? "Enter a valid email address." : null,
    password: !form.password ? "Enter your password." : null,
  };
  const show = (k) => (touched[k] ? errs[k] : null);

  const submit = async (e) => {
    e.preventDefault();
    setTouched({ email: true, password: true });
    if (errs.email || errs.password) return;
    setBusy(true);
    setError(null);
    try {
      const user = await login(form.email.trim(), form.password);
      navigate(`/${user.role}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Sign in" subtitle="Welcome back. Sign in to continue your preparation.">
      <form onSubmit={submit} className="space-y-5" noValidate>
        <ErrorBox message={error} />
        <Field label="Email" error={show("email")}>
          <input className="input h-11" type="email" autoComplete="email" required value={form.email} aria-invalid={!!show("email")}
            placeholder="you@college.edu" onBlur={() => setTouched((t) => ({ ...t, email: true }))}
            onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </Field>
        <div>
          <PasswordField id="login-password" label="Password" error={show("password")} autoComplete="current-password" required
            value={form.password} onBlur={() => setTouched((t) => ({ ...t, password: true }))}
            onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <p className="mt-2 text-right text-[13px]">
            <Link className="font-medium text-brand-600 hover:underline" to="/forgot-password">Forgot password?</Link>
          </p>
        </div>
        <Button type="submit" size="lg" className="w-full" loading={busy}>Sign in</Button>
      </form>
      {DEMO_ACCOUNTS.length > 0 && (
        <div className="mt-6 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3">
          <p className="text-xs font-medium text-slate-600">Demo accounts <span className="font-normal text-slate-400">(local development only)</span></p>
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {DEMO_ACCOUNTS.map((a) => (
              <button key={a.role} type="button" title={`${a.email} / ${a.password}`}
                onClick={() => { setForm({ email: a.email, password: a.password }); setTouched({}); setError(null); }}
                className="h-8 rounded-md border border-slate-200 bg-white text-xs font-medium text-slate-700 transition-colors hover:border-brand-500 hover:text-brand-600">
                {a.role}
              </button>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-slate-400">Fills the form - then press Sign in.</p>
        </div>
      )}
      <div className="mt-8 border-t border-slate-200 pt-6 text-center">
        <p className="text-sm text-slate-600">
          New student or recruiter? <Link className="font-medium text-brand-600 hover:underline" to="/register">Create an account</Link>
        </p>
        <p className="mt-2 text-xs text-slate-400">Mentor and admin accounts are created by the placement office.</p>
      </div>
    </AuthShell>
  );
}
