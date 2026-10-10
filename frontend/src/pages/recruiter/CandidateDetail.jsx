import { useState } from "react";
import { useParams } from "react-router-dom";
import { Download } from "lucide-react";
import { download, get } from "../../api";
import { Button, Card, ErrorBox, Modal, Notice, PageHeader, Pill, ScoreBar, Spinner, StatCard, StatusPill, Table, fmtDate, useApi, useToast } from "../../components/ui";
import { ResumeAnalysisView } from "../student/Resume";
import { InterviewReport } from "../student/InterviewSession";

export default function CandidateDetail() {
  const { id } = useParams();
  const toast = useToast();
  const [interview, setInterview] = useState(null);
  const { data, error, loading, reload } = useApi(() => get(`/recruiter/candidates/${id}`), [id]);
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const s = data.summary;
  const st = s.student;

  return (
    <div className="space-y-6">
      <PageHeader title={st.full_name} subtitle={`${st.college || "—"} · ${st.branch || "—"} · Class of ${st.graduation_year || "—"}${st.email ? ` · ${st.email}` : ""}`}
        actions={data.resume && <Button variant="secondary" onClick={() => download(`/resumes/${data.resume.id}/download`, data.resume.filename).catch((e) => toast(e.message, "error"))}><Download size={16} /> Resume</Button>} />
      {data.notice && <Notice tone="blue">{data.notice}</Notice>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="CGPA" value={st.cgpa ?? "—"} />
        <StatCard label="Interview average" value={s.interviews.average_score ?? "—"} hint={`${s.interviews.completed} interviews`} tone="sky" />
        <StatCard label="English average" value={s.english.average_score ?? "—"} hint={`${s.english.minutes} min practice`} tone="green" />
        <StatCard label="Assessment average" value={s.assessments.average_score != null ? `${s.assessments.average_score}%` : "—"} hint={`${s.assessments.passed} passed`} tone="violet" />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Skills"><div className="flex flex-wrap gap-1">{st.skills.length ? st.skills.map((x) => <Pill key={x} tone="brand">{x}</Pill>) : <span className="text-sm text-slate-500">None listed</span>}</div>
          {st.target_role && <p className="mt-3 text-sm text-slate-600">Target role: <b>{st.target_role}</b></p>}</Card>
        <Card title="Interview performance by area">
          <div className="space-y-2">{Object.entries(s.interviews.by_category).map(([k, v]) => <ScoreBar key={k} label={k} value={v} />)}
            {Object.keys(s.interviews.by_category).length === 0 && <p className="text-sm text-slate-500">No interviews yet.</p>}</div>
        </Card>
      </div>
      {data.profile && (data.profile.projects.length > 0 || data.profile.experience.length > 0) && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Projects">{data.profile.projects.map((p, i) => <div key={i} className="mb-2 text-sm"><p className="font-medium">{p.name}</p><p className="text-slate-600">{p.description}</p></div>)}</Card>
          <Card title="Experience">{data.profile.experience.map((e, i) => <div key={i} className="mb-2 text-sm"><p className="font-medium">{e.role} · {e.organization}</p><p className="text-slate-600">{e.summary}</p></div>)}</Card>
        </div>
      )}
      {data.full_access && (
        <>
          {data.applications?.length > 0 && (
            <Card title="Applications to your jobs">
              <ul className="space-y-1 text-sm">{data.applications.map((a) => <li key={a.id}>{a.job.title} · <StatusPill status={a.status} /> · applied {fmtDate(a.created_at)}</li>)}</ul>
            </Card>
          )}
          <Card title="Mock interview reports" bodyClass="">
            <Table rows={data.interviews} empty="No completed interviews" onRowClick={setInterview} columns={[
              { label: "Role", key: "job_role" }, { label: "Focus", key: "category" },
              { label: "Score", render: (r) => r.overall_score ?? "—" }, { label: "Date", render: (r) => fmtDate(r.completed_at) },
              { label: "", render: (r) => r.flagged ? <Pill tone="red">flagged</Pill> : null },
            ]} />
          </Card>
          {data.resume?.analysis && <><h2 className="text-lg font-semibold">Resume analysis</h2><ResumeAnalysisView resume={data.resume} /></>}
        </>
      )}
      <Modal open={!!interview} onClose={() => setInterview(null)} title={interview ? `${interview.job_role} · ${interview.category}` : ""} wide>
        {interview && <InterviewReport session={interview} />}
      </Modal>
    </div>
  );
}
