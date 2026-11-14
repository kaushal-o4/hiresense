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
import { post } from "../apiClient";
import { Button, ErrorBox, Field, Notice } from "../components/SharedUiComponents";
import AuthShell from "./AuthShell";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
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
        <Notice tone="sky">{done}</Notice>
      ) : (
        <form onSubmit={submit} className="space-y-4" noValidate>
          <ErrorBox message={error} />
          <Field label="Email">
            <input className="input" type="email" autoComplete="email" required value={email} autoFocus
              onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Button type="submit" size="lg" className="w-full" loading={busy} disabled={!email.trim()}>Send reset link</Button>
        </form>
      )}
      <p className="mt-6 text-center text-sm text-slate-600">
        <Link className="font-medium text-brand-600 hover:underline" to="/login">Back to sign in</Link>
      </p>
    </AuthShell>
  );
}
