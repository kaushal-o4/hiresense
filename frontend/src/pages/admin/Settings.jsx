import { useState } from "react";
import { get, put } from "../../api";
import { useAuth } from "../../auth";
import { Button, Card, ErrorBox, PageHeader, Spinner, useApi, useToast } from "../../components/ui";

function SettingRow({ s, onSaved }) {
  const toast = useToast();
  const [value, setValue] = useState(s.value);
  const [busy, setBusy] = useState(false);
  const isBool = typeof s.value === "boolean";
  const save = async (v) => {
    setBusy(true);
    try { await put(`/admin/settings/${s.key}`, { value: v }); toast("Setting saved"); onSaved(); } catch (e) { toast(e.message, "error"); setValue(s.value); } finally { setBusy(false); }
  };
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 py-4">
      <div><p className="font-medium"><code className="text-sm">{s.key}</code></p><p className="text-sm text-slate-500">{s.description}</p></div>
      {isBool ? (
        <button role="switch" aria-checked={value} aria-label={s.key} disabled={busy} onClick={() => { setValue(!value); save(!value); }}
          className={`relative h-6 w-11 rounded-full transition ${value ? "bg-brand-600" : "bg-slate-300"}`}>
          <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition ${value ? "left-5" : "left-0.5"}`} />
        </button>
      ) : (
        <div className="flex gap-2">
          <input className="input w-28" type="number" min="0" value={value} onChange={(e) => setValue(e.target.value)} aria-label={s.key} />
          <Button size="sm" loading={busy} onClick={() => save(Number(value))}>Save</Button>
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
      <PageHeader title="Platform settings" />
      {loading && <Spinner />}
      <ErrorBox message={error} onRetry={reload} />
      {data && <Card bodyClass="divide-y divide-slate-100 px-5">{data.map((s) => <SettingRow key={s.key} s={s} onSaved={() => { reload(); refresh(); }} />)}</Card>}
      <Card title="Server configuration">
        <p className="text-sm text-slate-600">Server configuration such as the local AI model, database URL and token signing key are configured in <code>backend/.env</code> on the server and are never exposed to the browser. Restart the backend after changing them.</p>
      </Card>
    </div>
  );
}
