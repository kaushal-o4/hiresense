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
import AuthShell from "./AuthShell";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
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
    <AuthShell title="Sign in" subtitle="Welcome back! Sign in to your HireSense account.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <ErrorBox message={error} />
        <Field label="Email">
          <input className="input" type="email" autoComplete="email" required value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </Field>
        <Field label="Password">
          <input className="input" type="password" autoComplete="current-password" required value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </Field>
        <p className="-mt-2 text-right text-sm">
          <Link className="text-brand-600 hover:underline" to="/forgot-password">Forgot password?</Link>
        </p>
        <Button type="submit" size="lg" className="w-full" loading={busy} disabled={!form.email || !form.password}>Sign in</Button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-600">
        New student or recruiter? <Link className="font-medium text-brand-600 hover:underline" to="/register">Create an account</Link>
      </p>
      <p className="mt-2 text-center text-xs text-slate-400">Mentor and admin accounts are created by the placement office.</p>
    </AuthShell>
  );
}
