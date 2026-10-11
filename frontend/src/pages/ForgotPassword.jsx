import { useState } from "react";
import { Link } from "react-router-dom";
import { post } from "../api";
import { Button, ErrorBox, Field, Notice } from "../components/ui";
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
          <Button type="submit" className="w-full" loading={busy} disabled={!email.trim()}>Send reset link</Button>
        </form>
      )}
      <p className="mt-6 text-center text-sm text-slate-600">
        <Link className="font-medium text-brand-600 hover:underline" to="/login">Back to sign in</Link>
      </p>
    </AuthShell>
  );
}
