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
import { CheckCircle2 } from "lucide-react";
import { post } from "../apiClient";
import { Button, ErrorBox, Notice, buttonClass } from "../components/SharedUiComponents";
import AuthShell, { PasswordField } from "./AuthShell";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [pw, setPw] = useState({ password: "", confirm: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [mismatch, setMismatch] = useState(false);
  const [done, setDone] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    if (pw.password !== pw.confirm) { setError(null); setMismatch(true); return; }
    setMismatch(false);
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
        <div className="space-y-5">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600"><CheckCircle2 size={19} /></span>
            <p className="mt-3 text-sm leading-relaxed text-slate-700" role="status">{done}</p>
          </div>
          <Link className={`${buttonClass("primary", "lg")} w-full`} to="/login">Sign in</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-5" noValidate>
          <ErrorBox message={error} />
          <PasswordField id="reset-new" label="New password" autoComplete="new-password" required value={pw.password} autoFocus
            onChange={(e) => { setPw({ ...pw, password: e.target.value }); setMismatch(false); }} />
          <PasswordField id="reset-confirm" label="Confirm new password" error={mismatch ? "The passwords do not match." : null}
            autoComplete="new-password" required value={pw.confirm}
            onChange={(e) => { setPw({ ...pw, confirm: e.target.value }); setMismatch(false); }} />
          <Button type="submit" size="lg" className="w-full" loading={busy} disabled={!pw.password || !pw.confirm}>Save new password</Button>
          {error && /expired|invalid/i.test(error) && (
            <p className="text-center text-sm"><Link className="font-medium text-brand-600 hover:underline" to="/forgot-password">Request a new link</Link></p>
          )}
        </form>
      )}
    </AuthShell>
  );
}
