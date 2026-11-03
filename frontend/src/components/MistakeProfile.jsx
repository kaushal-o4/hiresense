/*
 * "Mistakes you often make": the student's own recurring-mistake patterns (GET /student/english/profile).
 * They are counted from corrections Aria already gave, by simple rules, so the labels are approximate - the student
 * can dismiss any pattern or clear them all. Renders nothing until at least one pattern exists.
 */
import { useState } from "react";
import { del, get, post } from "../api";
import { Button, Card, useApi, useToast } from "./ui";

export default function MistakeProfile() {
  const toast = useToast();
  const { data, setData } = useApi(() => get("/student/english/profile"), []);
  const [busy, setBusy] = useState(false);
  if (!data || data.patterns.length === 0) return null;

  const run = async (fn) => {
    setBusy(true);
    try { setData(await fn()); } catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };

  return (
    <Card title="Mistakes you often make"
      actions={<Button variant="secondary" loading={busy} onClick={() => run(() => del("/student/english/profile"))}>Clear all</Button>}>
      <p className="mb-3 text-xs text-slate-500">
        Counted from corrections in your practice sessions, using simple rules, so it can be wrong. {data.rule}{" "}
        In “English learning” mode Aria gently practises your recurring ones.
      </p>
      <ul className="space-y-3">
        {data.patterns.map((p) => (
          <li key={p.id} className="flex items-start justify-between gap-3 text-sm">
            <div>
              <p className="font-medium text-slate-800">
                {p.label}{" "}
                <span className={`ml-1 rounded-full px-2 py-0.5 text-xs ${p.recurring ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-600"}`}>
                  {p.recurring ? "recurring" : "seen"}
                </span>
              </p>
              <p className="text-xs text-slate-500">{p.count} correction{p.count === 1 ? "" : "s"} in {p.sessions} session{p.sessions === 1 ? "" : "s"}</p>
              {p.example_original && (
                <p className="mt-1 text-xs"><span className="text-red-600 line-through">{p.example_original}</span> → <span className="font-medium text-emerald-700">{p.example_corrected}</span></p>
              )}
            </div>
            <button type="button" disabled={busy} className="shrink-0 text-xs text-slate-500 underline hover:text-slate-800"
              onClick={() => run(() => post(`/student/english/profile/${p.id}/dismiss`))}>This is wrong</button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
