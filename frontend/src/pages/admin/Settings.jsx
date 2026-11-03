/* Platform settings editor (PUT /admin/settings/{key}). */

import { useState } from "react";
import { get, put } from "../../api";
import { useAuth } from "../../auth";
import { Button, Card, ErrorBox, PageHeader, Spinner, useApi, useToast } from "../../components/ui";

// "ai_features_enabled" -> "AI features enabled"
const humanize = (key) => key.replace(/_/g, " ").replace(/\bai\b/g, "AI").replace(/^./, (c) => c.toUpperCase());

function SettingRow({ s, onSaved }) {
  const toast = useToast();
  const [value, setValue] = useState(s.value);
  const [busy, setBusy] = useState(false);
  const isBool = typeof s.value === "boolean";
  const options = Array.isArray(s.options) && s.options.length ? s.options : null;
  const save = async (v) => {
    setBusy(true);
    try { await put(`/admin/settings/${s.key}`, { value: v }); toast("Setting saved"); onSaved(); } catch (e) { toast(e.message, "error"); setValue(s.value); } finally { setBusy(false); }
  };
  const label = humanize(s.key);
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 py-4">
      <div className="min-w-0 flex-1 basis-64">
        <p className="text-sm font-medium text-slate-900">{label}</p>
        <p className="text-sm text-slate-500">{s.description}</p>
        <code className="mt-0.5 block text-[11px] text-slate-400">{s.key}</code>
      </div>
      {isBool ? (
        <button role="switch" aria-checked={value} aria-label={label} disabled={busy} onClick={() => { setValue(!value); save(!value); }}
          className={`relative h-6 w-11 shrink-0 rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 disabled:opacity-60 ${value ? "bg-brand-500" : "bg-slate-300"}`}>
          <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-snow shadow-soft transition-all ${value ? "left-[22px]" : "left-0.5"}`} />
        </button>
      ) : options ? (
        <select className="input w-40 capitalize" value={value ?? ""} disabled={busy} aria-label={label}
          onChange={(e) => { setValue(e.target.value); save(e.target.value); }}>
          {options.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : (
        <div className="flex gap-2">
          <input className="input w-28" type="number" min="0" value={value} onChange={(e) => setValue(e.target.value)} aria-label={label} />
          <Button size="sm" className="h-9" variant={String(value) === String(s.value) ? "secondary" : "primary"}
            disabled={value === "" || String(value) === String(s.value)} loading={busy} onClick={() => save(Number(value))}>Save</Button>
        </div>
      )}
    </div>
  );
}

export default function AdminSettings() {
  const { refresh } = useAuth();
  const { data, error, loading, reload } = useApi(() => get("/admin/settings"));
  return (
    <div className="space-y-6">
      <PageHeader title="Platform settings" subtitle="Changes apply immediately to every portal. Switches and choices save as soon as you change them." />
      {loading && <Spinner />}
      <ErrorBox message={error} onRetry={reload} />
      {data && <Card bodyClass="divide-y divide-slate-100 px-5">{data.map((s) => <SettingRow key={s.key} s={s} onSaved={() => { reload(); refresh(); }} />)}</Card>}
      <Card title="Server configuration">
        <p className="text-sm text-slate-600">Server configuration such as the local AI model, database URL and token signing key are configured in <code>backend/.env</code> on the server and are never exposed to the browser. Restart the backend after changing them.</p>
      </Card>
    </div>
  );
}
