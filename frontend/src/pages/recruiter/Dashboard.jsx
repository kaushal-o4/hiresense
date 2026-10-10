import { Link } from "react-router-dom";
import { Briefcase, CalendarClock, CheckCircle2, Plus, Users } from "lucide-react";
import { get } from "../../api";
import { MultiBar } from "../../components/charts";
import { Button, Card, ErrorBox, PageHeader, Spinner, StatCard, StatusPill, Table, fmtDateTime, useApi } from "../../components/ui";

export default function RecruiterDashboard() {
  const { data, error, loading, reload } = useApi(() => get("/recruiter/dashboard"));
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const bs = data.applications.by_status;
  return (
    <div className="space-y-6">
      <PageHeader title="Recruitment dashboard" subtitle="Your jobs, candidates and hiring progress."
        actions={<Link to="/recruiter/jobs?new=1"><Button><Plus size={16} /> Post a job</Button></Link>} />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Active jobs" value={data.jobs.published} icon={Briefcase} hint={`${data.jobs.draft} drafts · ${data.jobs.closed} closed`} />
        <StatCard label="Applications" value={data.applications.total} icon={Users} tone="sky" hint={`${bs.applied || 0} awaiting review`} />
        <StatCard label="Shortlisted" value={(bs.shortlisted || 0) + (bs.interview_scheduled || 0)} icon={CalendarClock} tone="amber" hint={`${bs.interview_scheduled || 0} interviews scheduled`} />
        <StatCard label="Selected" value={bs.selected || 0} icon={CheckCircle2} tone="green" hint={`${bs.rejected || 0} not selected`} />
      </div>
      <Card title="Hiring funnel by job">
        <MultiBar data={data.per_job.map((j) => ({ ...j, name: j.title.length > 18 ? `${j.title.slice(0, 18)}…` : j.title }))} nameKey="name"
          keys={[{ key: "applications", label: "Applications" }, { key: "shortlisted", label: "Shortlisted" }, { key: "selected", label: "Selected" }]} />
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Recent applications" bodyClass="">
          <Table rows={data.recent_applications} empty="No applications yet"
            columns={[
              { label: "Candidate", render: (a) => <Link className="font-medium text-brand-700 hover:underline" to={`/recruiter/candidates/${a.student_id}`}>{a.student?.full_name}</Link> },
              { label: "Job", render: (a) => <Link className="hover:underline" to={`/recruiter/jobs/${a.job_id}`}>{a.job?.title}</Link> },
              { label: "Match", render: (a) => a.match?.score ?? "—" },
              { label: "Status", render: (a) => <StatusPill status={a.status} /> },
            ]} />
        </Card>
        <Card title="Upcoming interviews" bodyClass="">
          <Table rows={data.upcoming_interviews} empty="No interviews scheduled"
            columns={[
              { label: "Candidate", render: (a) => a.student?.full_name },
              { label: "Job", render: (a) => a.job?.title },
              { label: "When", render: (a) => fmtDateTime(a.interview_at) },
            ]} />
        </Card>
      </div>
    </div>
  );
}
