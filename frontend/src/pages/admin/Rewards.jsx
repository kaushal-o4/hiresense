import { useState } from "react";
import { Plus } from "lucide-react";
import { get, patch, post, put } from "../../api";
import { Button, Card, ErrorBox, Field, Modal, PageHeader, Pill, Spinner, Table, useApi, useToast } from "../../components/ui";

const CRITERIA = ["interviews_completed", "english_minutes", "avg_interview_score", "technical_best_score", "streak_days",
  "assessments_passed", "english_sessions", "high_score_interviews", "english_avg_score"];

export default function AdminRewards() {
  const toast = useToast();
  const badges = useApi(() => get("/admin/badges"));
  const rules = useApi(() => get("/admin/reward-rules"));
  const [badge, setBadge] = useState(null);
  const [rule, setRule] = useState(null);

  const saveBadge = async () => {
    try {
      const body = { code: badge.code, name: badge.name, description: badge.description, icon: badge.icon, criteria_type: badge.criteria_type,
        threshold: Number(badge.threshold), points: Number(badge.points), active: badge.active };
      if (badge.id) await put(`/admin/badges/${badge.id}`, body); else await post("/admin/badges", body);
      toast("Badge saved"); setBadge(null); badges.reload();
    } catch (e) { toast(e.message, "error"); }
  };

  const saveRule = async () => {
    try {
      let requirements;
      try { requirements = JSON.parse(rule.requirementsText || "{}"); } catch { throw new Error("Requirements must be valid JSON, e.g. {\"min_answers\": 3}"); }
      await patch(`/admin/reward-rules/${rule.id}`, { points: Number(rule.points), daily_cap: Number(rule.daily_cap), active: rule.active, description: rule.description, requirements });
      toast("Rule saved"); setRule(null); rules.reload();
    } catch (e) { toast(e.message, "error"); }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Rewards, badges & points" subtitle="Configure how students earn points and achievements. Changes apply to future activity." />
      <Card title="Point rules" bodyClass="">
        {rules.loading && <Spinner />}<ErrorBox message={rules.error} />
        {rules.data && <Table rows={rules.data} columns={[
          { label: "Activity", render: (r) => <div><code className="text-xs">{r.activity_type}</code><p className="text-xs text-slate-500">{r.description}</p></div> },
          { label: "Points", key: "points" }, { label: "Daily cap", key: "daily_cap" },
          { label: "Requirements", render: (r) => <code className="text-xs">{JSON.stringify(r.requirements)}</code> },
          { label: "Status", render: (r) => <Pill tone={r.active ? "green" : "gray"}>{r.active ? "active" : "off"}</Pill> },
          { label: "", render: (r) => <Button size="sm" variant="ghost" onClick={() => setRule({ ...r, requirementsText: JSON.stringify(r.requirements) })}>Edit</Button> }]} />}
      </Card>
      <Card title="Badges" bodyClass="" actions={<Button size="sm" onClick={() => setBadge({ code: "", name: "", description: "", icon: "🏅", criteria_type: "interviews_completed", threshold: 1, points: 50, active: true })}><Plus size={14} /> New badge</Button>}>
        {badges.loading && <Spinner />}<ErrorBox message={badges.error} />
        {badges.data && <Table rows={badges.data} columns={[
          { label: "Badge", render: (b) => <span className="flex items-center gap-2"><span className="text-xl">{b.icon}</span><span><b>{b.name}</b><br /><span className="text-xs text-slate-500">{b.description}</span></span></span> },
          { label: "Criterion", render: (b) => <span className="text-xs">{b.criteria_type.replace(/_/g, " ")} ≥ {b.threshold}</span> },
          { label: "Points", key: "points" }, { label: "Awarded", key: "awarded" },
          { label: "Status", render: (b) => <Pill tone={b.active ? "green" : "gray"}>{b.active ? "active" : "off"}</Pill> },
          { label: "", render: (b) => <Button size="sm" variant="ghost" onClick={() => setBadge(b)}>Edit</Button> }]} />}
      </Card>

      <Modal open={!!badge} onClose={() => setBadge(null)} title={badge?.id ? "Edit badge" : "New badge"} footer={<Button onClick={saveBadge}>Save</Button>}>
        {badge && <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Code"><input className="input" disabled={!!badge.id} value={badge.code} onChange={(e) => setBadge({ ...badge, code: e.target.value })} /></Field>
          <Field label="Icon (emoji)"><input className="input" value={badge.icon} onChange={(e) => setBadge({ ...badge, icon: e.target.value })} /></Field>
          <div className="sm:col-span-2"><Field label="Name"><input className="input" value={badge.name} onChange={(e) => setBadge({ ...badge, name: e.target.value })} /></Field></div>
          <div className="sm:col-span-2"><Field label="Description"><input className="input" value={badge.description} onChange={(e) => setBadge({ ...badge, description: e.target.value })} /></Field></div>
          <Field label="Criterion"><select className="input" value={badge.criteria_type} onChange={(e) => setBadge({ ...badge, criteria_type: e.target.value })}>{CRITERIA.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}</select></Field>
          <Field label="Threshold"><input className="input" type="number" min="0" value={badge.threshold} onChange={(e) => setBadge({ ...badge, threshold: e.target.value })} /></Field>
          <Field label="Bonus points"><input className="input" type="number" min="0" value={badge.points} onChange={(e) => setBadge({ ...badge, points: e.target.value })} /></Field>
          <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={badge.active} onChange={(e) => setBadge({ ...badge, active: e.target.checked })} /> Active</label>
        </div>}
      </Modal>
      <Modal open={!!rule} onClose={() => setRule(null)} title={`Edit rule · ${rule?.activity_type}`} footer={<Button onClick={saveRule}>Save</Button>}>
        {rule && <div className="space-y-3">
          <Field label="Description"><input className="input" value={rule.description} onChange={(e) => setRule({ ...rule, description: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Points"><input className="input" type="number" min="0" value={rule.points} onChange={(e) => setRule({ ...rule, points: e.target.value })} /></Field>
            <Field label="Max awards per day"><input className="input" type="number" min="0" value={rule.daily_cap} onChange={(e) => setRule({ ...rule, daily_cap: e.target.value })} /></Field>
          </div>
          <Field label="Requirements (JSON)" hint="interview_completed: min_answers, min_words_per_answer · english_session: min_active_seconds · score_improvement: min_improvement">
            <input className="input font-mono" value={rule.requirementsText} onChange={(e) => setRule({ ...rule, requirementsText: e.target.value })} />
          </Field>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={rule.active} onChange={(e) => setRule({ ...rule, active: e.target.checked })} /> Active</label>
        </div>}
      </Modal>
    </div>
  );
}
