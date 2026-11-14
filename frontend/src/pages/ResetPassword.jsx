// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/ResetPassword.jsx
//
// FILE PURPOSE:
// Page that sets a new password from the emailed reset link.
//
// WHAT THIS FILE DOES:
// 1. Reads the token from the URL (?token=...).
// 2. Asks for the new password twice.
// 3. Calls POST /auth/reset-password.
//
// HOW THIS FILE WORKS:
// A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and
// modal state with useState, sends changes with post/put/patch/del and shows the result with the
// shared components from SharedUiComponents.jsx. API calls used: POST /auth/reset-password.
//
// IMPORTANT FUNCTIONS:
//    - ResetPassword()
//        Form component.
//
// INPUT:
// Token from the URL and the new password.
//
// OUTPUT:
// Password changed message.
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
/* Set a new password from an emailed reset link (POST /auth/reset-password with the token from the URL). */

import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { post } from "../apiClient";
import { Button, ErrorBox, Field, Notice } from "../components/SharedUiComponents";
import AuthShell from "./AuthShell";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [pw, setPw] = useState({ password: "", confirm: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    if (pw.password !== pw.confirm) return setError("The passwords do not match");
    setBusy(true);
    setError(null);
    try {
      const r = await post("/auth/reset-password", { token, new_password: pw.password });
      setDone(r.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Choose a new password" subtitle="At least 8 characters, with letters and numbers.">
      {!token ? (
        <Notice>This page needs the link from your reset email. <Link className="font-medium underline" to="/forgot-password">Request a new link</Link>.</Notice>
      ) : done ? (
        <div className="space-y-4">
          <Notice tone="sky">{done}</Notice>
          <Link className="flex w-full items-center justify-center h-11 rounded-xl px-4 text-[15px] font-medium bg-gradient-to-r from-brand-500 to-violet-500 text-snow shadow-glow hover:brightness-110" to="/login">Sign in</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" noValidate>
          <ErrorBox message={error} />
          <Field label="New password">
            <input className="input" type="password" autoComplete="new-password" required value={pw.password} autoFocus
              onChange={(e) => setPw({ ...pw, password: e.target.value })} />
          </Field>
          <Field label="Confirm new password">
            <input className="input" type="password" autoComplete="new-password" required value={pw.confirm}
              onChange={(e) => setPw({ ...pw, confirm: e.target.value })} />
          </Field>
          <Button type="submit" size="lg" className="w-full" loading={busy} disabled={!pw.password || !pw.confirm}>Save new password</Button>
          {error && /expired|invalid/i.test(error) && (
            <p className="text-center text-sm"><Link className="text-brand-600 hover:underline" to="/forgot-password">Request a new link</Link></p>
          )}
        </form>
      )}
    </AuthShell>
  );
}
