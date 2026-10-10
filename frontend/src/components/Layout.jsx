import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Award, BarChart3, Bell, BookOpen, Briefcase, CalendarClock, CalendarDays, ClipboardCheck, ClipboardList, FileBarChart,
  FileText, Gauge, GraduationCap, History, Languages, LayoutDashboard, LogOut, Megaphone, Menu, MessagesSquare, Mic,
  ScrollText, Search, Settings, ShieldAlert, SlidersHorizontal, Sparkles, Target, TrendingUp, User, Users, X,
} from "lucide-react";
import { useAuth } from "../auth";
import { get, post } from "../api";
import { fmtDateTime } from "./ui";

const NAV = {
  student: [
    { to: "/student", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/student/resume", label: "Resume Analysis", icon: FileText },
    { to: "/student/interviews", label: "Mock Interviews", icon: Mic },
    { to: "/student/english", label: "English Conversation", icon: MessagesSquare },
    { to: "/student/english-learning", label: "Speaking Practice", icon: Languages },
    { to: "/student/assessments", label: "Assessments", icon: ClipboardCheck },
    { to: "/student/progress", label: "Progress", icon: BarChart3 },
    { to: "/student/report", label: "Performance Report", icon: FileBarChart },
    { to: "/student/history", label: "Practice History", icon: History },
    { to: "/student/rewards", label: "Rewards & Challenges", icon: Award },
    { to: "/student/jobs", label: "Jobs", icon: Briefcase },
    { to: "/student/applications", label: "My Applications", icon: ClipboardList },
    { to: "/student/drives", label: "Placement Drives", icon: CalendarDays },
    { to: "/student/mentoring", label: "Mentoring", icon: Target },
  ],
  recruiter: [
    { to: "/recruiter", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/recruiter/jobs", label: "Job Postings", icon: Briefcase },
    { to: "/recruiter/candidates", label: "Candidates", icon: Search },
    { to: "/recruiter/assessments", label: "Assessments", icon: ClipboardCheck },
  ],
  mentor: [
    { to: "/mentor", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/mentor/students", label: "My Students", icon: GraduationCap },
    { to: "/mentor/sessions", label: "Follow-up Sessions", icon: CalendarClock },
  ],
  admin: [
    { to: "/admin", label: "Analytics", icon: LayoutDashboard, end: true },
    { to: "/admin/users", label: "Users", icon: Users },
    { to: "/admin/assignments", label: "Mentor Assignments", icon: GraduationCap },
    { to: "/admin/jobs", label: "Jobs & Placements", icon: Briefcase },
    { to: "/admin/interview-config", label: "Interview Setup", icon: BookOpen },
    { to: "/admin/assessments", label: "Assessments", icon: ClipboardCheck },
    { to: "/admin/rewards", label: "Rewards & Badges", icon: Award },
    { to: "/admin/monitoring", label: "AI & Monitoring", icon: ShieldAlert },
    { to: "/admin/audit", label: "Audit Logs", icon: ScrollText },
    { to: "/admin/reports", label: "Reports", icon: Gauge },
    { to: "/admin/settings", label: "Settings", icon: Settings },
  ],
};

const ROLE_LABEL = { student: "Student", recruiter: "Recruiter", mentor: "Mentor", admin: "Administrator" };

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState({ items: [], unread: 0 });
  const ref = useRef(null);
  const navigate = useNavigate();

  const load = async () => {
    try {
      setData(await get("/notifications", { page_size: 8 }));
    } catch { /* ignore polling errors */ }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    const onClick = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", onClick);
    return () => { clearInterval(t); document.removeEventListener("mousedown", onClick); };
  }, []);

  const openItem = async (n) => {
    if (!n.read) await post(`/notifications/${n.id}/read`).catch(() => {});
    setOpen(false);
    load();
    if (n.link) navigate(n.link);
  };

  return (
    <div className="relative" ref={ref}>
      <button className="relative rounded-full p-2 text-slate-600 hover:bg-slate-100" onClick={() => { setOpen(!open); load(); }}
        aria-label={`Notifications (${data.unread} unread)`}>
        <Bell size={20} />
        {data.unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
            {data.unread > 99 ? "99+" : data.unread}
          </span>
        )}
      </button>
      {open && (
        <div className="card absolute right-0 z-40 mt-2 w-[22rem] max-w-[calc(100vw-2rem)]">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2">
            <span className="text-sm font-semibold">Notifications</span>
            {data.unread > 0 && (
              <button className="text-xs text-brand-600 hover:underline" onClick={async () => { await post("/notifications/read-all"); load(); }}>
                Mark all read
              </button>
            )}
          </div>
          <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
            {data.items.length === 0 && <li className="p-4 text-center text-sm text-slate-500">You're all caught up.</li>}
            {data.items.map((n) => (
              <li key={n.id}>
                <button className={`w-full px-4 py-3 text-left hover:bg-slate-50 ${n.read ? "" : "bg-brand-50/50"}`} onClick={() => openItem(n)}>
                  <p className="text-sm font-medium text-slate-800">{n.title}</p>
                  <p className="line-clamp-2 text-xs text-slate-600">{n.message}</p>
                  <p className="mt-1 text-[11px] text-slate-400">{fmtDateTime(n.created_at)}</p>
                </button>
              </li>
            ))}
          </ul>
          <Link to="/notifications" onClick={() => setOpen(false)} className="block border-t border-slate-100 py-2 text-center text-xs font-medium text-brand-600 hover:bg-slate-50">
            View all
          </Link>
        </div>
      )}
    </div>
  );
}

export default function Layout() {
  const { user, ai, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();
  const items = [...(NAV[user.role] || []),
    // only mentors explicitly authorised by an admin review interview monitoring
    ...(user.role === "mentor" && (user.permissions || []).includes("review_integrity")
      ? [{ to: "/mentor/integrity", label: "Integrity Review", icon: ShieldAlert }] : [])];

  const sidebar = (
    <nav className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white"><Sparkles size={18} /></div>
        <div>
          <p className="text-lg font-bold leading-tight text-white">HireSense</p>
          <p className="text-[11px] uppercase tracking-wider text-brand-200">{ROLE_LABEL[user.role]} portal</p>
        </div>
      </div>
      <ul className="flex-1 space-y-0.5 overflow-y-auto px-3">
        {items.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink to={to} end={end} onClick={() => setMobileOpen(false)}
              className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                isActive ? "bg-white/15 text-white" : "text-brand-100 hover:bg-white/10 hover:text-white"}`}>
              <Icon size={18} /> {label}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="border-t border-white/10 p-3">
        <NavLink to="/profile" onClick={() => setMobileOpen(false)}
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-brand-100 hover:bg-white/10 hover:text-white">
          <User size={18} /> Profile
        </NavLink>
        <NavLink to="/settings" onClick={() => setMobileOpen(false)}
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-brand-100 hover:bg-white/10 hover:text-white">
          <SlidersHorizontal size={18} /> Account settings
        </NavLink>
        <button onClick={async () => { await logout(); navigate("/login"); }}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-brand-100 hover:bg-white/10 hover:text-white">
          <LogOut size={18} /> Sign out
        </button>
      </div>
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 bg-gradient-to-b from-brand-900 to-brand-800 lg:block">{sidebar}</aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-gradient-to-b from-brand-900 to-brand-800">
            <button className="absolute right-3 top-5 text-white" onClick={() => setMobileOpen(false)} aria-label="Close menu"><X /></button>
            {sidebar}
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-6">
          <button className="rounded p-2 text-slate-600 hover:bg-slate-100 lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open menu">
            <Menu size={20} />
          </button>
          <div className="flex-1" />
          {ai && !ai.available && (
            <span className="hidden rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800 sm:inline">
              AI not configured
            </span>
          )}
          <NotificationBell />
          <Link to="/profile" className="flex items-center gap-2 rounded-full py-1 pl-1 pr-3 hover:bg-slate-100">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
              {user.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()}
            </span>
            <span className="hidden text-sm font-medium text-slate-700 sm:inline">{user.full_name}</span>
          </Link>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
