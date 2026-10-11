import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { Button, ErrorBox, Field } from "../components/ui";
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
        <Button type="submit" className="w-full" loading={busy} disabled={!form.email || !form.password}>Sign in</Button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-600">
        New student or recruiter? <Link className="font-medium text-brand-600 hover:underline" to="/register">Create an account</Link>
      </p>
      <p className="mt-2 text-center text-xs text-slate-400">Mentor and admin accounts are created by the placement office.</p>
    </AuthShell>
  );
}
