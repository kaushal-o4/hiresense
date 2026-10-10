import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BadgeCheck, Plus, Trash2 } from "lucide-react";
import { put } from "../api";
import { useAuth } from "../auth";
import { Button, Card, Field, PageHeader, Pill, TagInput, useToast } from "../components/ui";

function StudentFields({ p, setP }) {
  const set = (k) => (e) => setP({ ...p, [k]: e.target.value });
  const projects = p.projects || [];
  const experience = p.experience || [];
  const updList = (key, i, field, value) => {
    const list = [...(p[key] || [])];
    list[i] = { ...list[i], [field]: value };
    setP({ ...p, [key]: list });
  };
  return (
    <>
      <Card title="Education">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="College"><input className="input" value={p.college || ""} onChange={set("college")} /></Field>
          <Field label="Degree"><input className="input" placeholder="B.Tech" value={p.degree || ""} onChange={set("degree")} /></Field>
          <Field label="Branch"><input className="input" value={p.branch || ""} onChange={set("branch")} /></Field>
          <Field label="Graduation year"><input className="input" type="number" value={p.graduation_year || ""} onChange={set("graduation_year")} /></Field>
          <Field label="CGPA (0-10)"><input className="input" type="number" step="0.01" min="0" max="10" value={p.cgpa ?? ""} onChange={set("cgpa")} /></Field>
          <Field label="Phone"><input className="input" value={p.phone || ""} onChange={set("phone")} /></Field>
        </div>
      </Card>
      <Card title="Career">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Target role"><input className="input" placeholder="Software Engineer" value={p.target_role || ""} onChange={set("target_role")} /></Field>
          <Field label="LinkedIn URL"><input className="input" value={p.linkedin_url || ""} onChange={set("linkedin_url")} /></Field>
          <Field label="GitHub URL"><input className="input" value={p.github_url || ""} onChange={set("github_url")} /></Field>
          <div className="sm:col-span-2"><Field label="Skills"><TagInput value={p.skills || []} onChange={(skills) => setP({ ...p, skills })} /></Field></div>
          <div className="sm:col-span-2"><Field label="Career interests"><textarea className="input" rows={2} value={p.career_interests || ""} onChange={set("career_interests")} /></Field></div>
          <div className="sm:col-span-2"><Field label="About me"><textarea className="input" rows={3} value={p.bio || ""} onChange={set("bio")} /></Field></div>
        </div>
      </Card>
      <Card title="Projects" actions={<Button size="sm" variant="secondary" onClick={() => setP({ ...p, projects: [...projects, { name: "", description: "", technologies: [] }] })}><Plus size={14} /> Add</Button>}>
        {projects.length === 0 && <p className="text-sm text-slate-500">No projects yet.</p>}
        <div className="space-y-4">
          {projects.map((pr, i) => (
            <div key={i} className="grid gap-3 rounded-lg border border-slate-200 p-3 sm:grid-cols-2">
              <Field label="Name"><input className="input" value={pr.name} onChange={(e) => updList("projects", i, "name", e.target.value)} /></Field>
              <Field label="Technologies"><TagInput value={pr.technologies || []} onChange={(v) => updList("projects", i, "technologies", v)} /></Field>
              <div className="sm:col-span-2"><Field label="Description"><textarea className="input" rows={2} value={pr.description} onChange={(e) => updList("projects", i, "description", e.target.value)} /></Field></div>
              <div className="sm:col-span-2 text-right"><Button size="sm" variant="ghost" onClick={() => setP({ ...p, projects: projects.filter((_, j) => j !== i) })}><Trash2 size={14} /> Remove</Button></div>
            </div>
          ))}
        </div>
      </Card>
      <Card title="Experience & internships" actions={<Button size="sm" variant="secondary" onClick={() => setP({ ...p, experience: [...experience, { organization: "", role: "", duration: "", summary: "" }] })}><Plus size={14} /> Add</Button>}>
        {experience.length === 0 && <p className="text-sm text-slate-500">No experience added.</p>}
        <div className="space-y-4">
          {experience.map((ex, i) => (
            <div key={i} className="grid gap-3 rounded-lg border border-slate-200 p-3 sm:grid-cols-3">
              <Field label="Organization"><input className="input" value={ex.organization} onChange={(e) => updList("experience", i, "organization", e.target.value)} /></Field>
              <Field label="Role"><input className="input" value={ex.role} onChange={(e) => updList("experience", i, "role", e.target.value)} /></Field>
              <Field label="Duration"><input className="input" placeholder="Jun–Aug 2025" value={ex.duration} onChange={(e) => updList("experience", i, "duration", e.target.value)} /></Field>
              <div className="sm:col-span-3"><Field label="Summary"><textarea className="input" rows={2} value={ex.summary} onChange={(e) => updList("experience", i, "summary", e.target.value)} /></Field></div>
              <div className="sm:col-span-3 text-right"><Button size="sm" variant="ghost" onClick={() => setP({ ...p, experience: experience.filter((_, j) => j !== i) })}><Trash2 size={14} /> Remove</Button></div>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

function RecruiterFields({ p, setP }) {
  const set = (k) => (e) => setP({ ...p, [k]: e.target.value });
  return (
    <Card title="Company profile" actions={p.company_verified
      ? <Pill tone="green"><BadgeCheck size={14} className="mr-1" /> Verified by placement office</Pill>
      : <Pill tone="amber">Verification pending</Pill>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Company name" hint="Changing the name requires re-verification"><input className="input" value={p.company_name || ""} onChange={set("company_name")} /></Field>
        <Field label="Industry"><input className="input" placeholder="e.g. IT services, Fintech" value={p.industry || ""} onChange={set("industry")} /></Field>
        <Field label="Website"><input className="input" value={p.company_website || ""} onChange={set("company_website")} /></Field>
        <Field label="Your designation"><input className="input" value={p.designation || ""} onChange={set("designation")} /></Field>
        <Field label="Location"><input className="input" value={p.location || ""} onChange={set("location")} /></Field>
        <Field label="Phone"><input className="input" value={p.phone || ""} onChange={set("phone")} /></Field>
        <div className="sm:col-span-2"><Field label="About the company"><textarea className="input" rows={4} value={p.company_description || ""} onChange={set("company_description")} /></Field></div>
      </div>
    </Card>
  );
}

function MentorFields({ p, setP }) {
  return (
    <Card title="Mentor profile">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Department"><input className="input" value={p.department || ""} onChange={(e) => setP({ ...p, department: e.target.value })} /></Field>
        <Field label="Expertise"><TagInput value={p.expertise || []} onChange={(expertise) => setP({ ...p, expertise })} /></Field>
        <div className="sm:col-span-2"><Field label="Bio"><textarea className="input" rows={3} value={p.bio || ""} onChange={(e) => setP({ ...p, bio: e.target.value })} /></Field></div>
      </div>
    </Card>
  );
}

const NUMERIC = ["graduation_year", "cgpa"];

export default function Profile() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(user.full_name);
  const [p, setP] = useState(user.profile || {});
  const [busy, setBusy] = useState(false);

  useEffect(() => { setP(user.profile || {}); setName(user.full_name); }, [user]);

  const save = async () => {
    setBusy(true);
    try {
      const body = { full_name: name };
      if (user.role !== "admin") {
        Object.entries(p).forEach(([k, v]) => {
          if (NUMERIC.includes(k)) body[k] = v === "" || v == null ? null : Number(v);
          else if (!["max_students", "company_verified", "share_with_recruiters"].includes(k)) body[k] = v === "" ? null : v;
        });
        if (user.role === "student") {
          body.projects = (p.projects || []).filter((x) => x.name?.trim());
          body.experience = (p.experience || []).filter((x) => x.organization?.trim() && x.role?.trim());
        }
      }
      const updated = await put("/profile", body);
      setUser(updated);
      toast("Profile saved");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="My profile" subtitle={user.email} actions={<Button onClick={save} loading={busy}>Save changes</Button>} />
      <Card title="Account">
        <Field label="Full name"><input className="input max-w-md" value={name} onChange={(e) => setName(e.target.value)} /></Field>
      </Card>
      {user.role === "student" && <StudentFields p={p} setP={setP} />}
      {user.role === "recruiter" && <RecruiterFields p={p} setP={setP} />}
      {user.role === "mentor" && <MentorFields p={p} setP={setP} />}
      <div className="flex items-center justify-between">
        <Link to="/settings" className="text-sm text-brand-600 hover:underline">Password, language & privacy settings →</Link>
        <Button onClick={save} loading={busy}>Save changes</Button>
      </div>
    </div>
  );
}
