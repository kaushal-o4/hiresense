/* Shared application shell, navigation and notifications. */

import { Suspense, useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Award, BarChart3, Bell, BookOpen, Briefcase, CalendarClock, ClipboardCheck, ClipboardList,
  FileText, Gauge, GraduationCap, LayoutDashboard, LogOut, Menu, MessagesSquare, Mic,
  ScrollText, Search, Settings, ShieldAlert, SlidersHorizontal, Target, User, Users, X,
} from "lucide-react";
import { useAuth } from "../auth";
import { get, post } from "../api";
import Logo from "./Logo";
import { fmtDateTime, Spinner } from "./ui";

// `section` starts a new labelled group in the sidebar.
const NAV = {
  student: [
    { to: "/student", label: "Dashboard", icon: LayoutDashboard, end: true },
    { section: "Practice" },
    { to: "/student/interviews", label: "Mock interviews", icon: Mic },
    { to: "/student/english", label: "English conversation", icon: MessagesSquare },
    { to: "/student/assessments", label: "Assessments", icon: ClipboardCheck },
    { to: "/student/resume", label: "Resume analysis", icon: FileText },
    { section: "Progress" },
    { to: "/student/progress", label: "My progress", icon: BarChart3 }, // overview, full report, practice history
    { to: "/student/rewards", label: "Rewards & challenges", icon: Award },
    { section: "Career" },
    { to: "/student/jobs", label: "Jobs & drives", icon: Briefcase }, // job openings + placement drives
    { to: "/student/applications", label: "My applications", icon: ClipboardList },
    { to: "/student/mentoring", label: "Mentoring", icon: Target },
  ],
  recruiter: [
    { to: "/recruiter", label: "Dashboard", icon: LayoutDashboard, end: true },
    { section: "Hiring" },
    { to: "/recruiter/jobs", label: "Job postings", icon: Briefcase },
    { to: "/recruiter/candidates", label: "Candidates", icon: Search },
    { to: "/recruiter/assessments", label: "Assessments", icon: ClipboardCheck },
    { to: "/recruiter/security", label: "Security reports", icon: ShieldAlert },
  ],
  mentor: [
    { to: "/mentor", label: "Dashboard", icon: LayoutDashboard, end: true },
    { section: "Mentoring" },
    { to: "/mentor/students", label: "My students", icon: GraduationCap },
    { to: "/mentor/sessions", label: "Follow-up sessions", icon: CalendarClock },
  ],
  admin: [
    { to: "/admin", label: "Analytics", icon: LayoutDashboard, end: true },
    { section: "People" },
    { to: "/admin/users", label: "Users", icon: Users },
    { to: "/admin/assignments", label: "Mentor assignments", icon: GraduationCap },
    { section: "Programme" },
    { to: "/admin/jobs", label: "Jobs & placements", icon: Briefcase },
    { to: "/admin/interview-config", label: "Interview setup", icon: BookOpen },
    { to: "/admin/assessments", label: "Assessments", icon: ClipboardCheck },
    { to: "/admin/rewards", label: "Rewards & badges", icon: Award },
    { section: "System" },
    { to: "/admin/monitoring", label: "AI & monitoring", icon: ShieldAlert },
    { to: "/admin/audit", label: "Audit logs", icon: ScrollText },
    { to: "/admin/reports", label: "Reports", icon: Gauge },
    { to: "/admin/settings", label: "Settings", icon: Settings },
  ],
};

const ROLE_LABEL = { student: "Student", recruiter: "Recruiter", mentor: "Mentor", admin: "Admin" };

const initials = (name = "") => name.split(" ").filter(Boolean).map((p) => p[0]).slice(0, 2).join("").toUpperCase();

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
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      clearInterval(t);
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const openItem = async (n) => {
    if (!n.read) await post(`/notifications/${n.id}/read`).catch(() => {});
    setOpen(false);
    load();
    if (n.link) navigate(n.link);
  };

  return (
    <div className="relative" ref={ref}>
      <button className={`relative flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 ${open ? "bg-slate-100 text-slate-900" : ""}`}
        onClick={() => { setOpen(!open); load(); }}
        aria-label={`Notifications (${data.unread} unread)`} aria-expanded={open} aria-haspopup="true">
        <Bell size={18} />
        {data.unread > 0 && (
          <span className="num absolute right-1 top-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-brand-600 px-1 text-[10px] font-semibold text-snow ring-2 ring-white">
            {data.unread > 99 ? "99+" : data.unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-[22rem] max-w-[calc(100vw-2rem)] animate-fade-up overflow-hidden rounded-xl border border-slate-200 bg-white shadow-pop">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <span className="text-sm font-semibold">Notifications</span>
            {data.unread > 0 && (
              <button className="text-xs font-medium text-slate-500 hover:text-slate-900" onClick={async () => { await post("/notifications/read-all"); load(); }}>
                Mark all as read
              </button>
            )}
          </div>
          <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
            {data.items.length === 0 && <li className="px-4 py-8 text-center text-sm text-slate-500">You're all caught up.</li>}
            {data.items.map((n) => (
              <li key={n.id}>
                <button className="flex w-full gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-50" onClick={() => openItem(n)}>
                  <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.read ? "bg-transparent" : "bg-brand-500"}`} aria-hidden />
                  <span className="min-w-0">
                    <span className={`block text-sm ${n.read ? "text-slate-700" : "font-medium text-slate-900"}`}>{n.title}</span>
                    <span className="line-clamp-2 block text-xs text-slate-500">{n.message}</span>
                    <span className="mt-1 block text-[11px] text-slate-400">{fmtDateTime(n.created_at)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <Link to="/notifications" onClick={() => setOpen(false)} className="block border-t border-slate-100 py-2.5 text-center text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900">
            View all notifications
          </Link>
        </div>
      )}
    </div>
  );
}

const navItemClass = ({ isActive }) => `group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] transition ${
  isActive ? "bg-gradient-to-r from-brand-500/20 to-violet-500/5 font-medium text-slate-950 ring-1 ring-inset ring-brand-400/25"
    : "text-slate-600 hover:bg-slate-200/40 hover:text-slate-900"}`;

export default function Layout() {
  const { user, ai, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();
  // Escape closes the mobile menu, like clicking the dark backdrop does.
  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e) => e.key === "Escape" && setMobileOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mobileOpen]);
  const items = [...(NAV[user.role] || []),
    // only mentors explicitly authorised by an admin review interview monitoring
    ...(user.role === "mentor" && (user.permissions || []).includes("review_integrity")
      ? [{ to: "/mentor/integrity", label: "Integrity review", icon: ShieldAlert }] : [])];
  const close = () => setMobileOpen(false);

  const sidebar = (
    <nav className="flex h-full flex-col" aria-label="Main">
      <div className="flex h-14 items-center gap-2 px-4">
        <Link to={`/${user.role}`} onClick={close} className="rounded-md focus-visible:outline-offset-4"><Logo size={26} /></Link>
        <span className="rounded-md border border-brand-400/30 bg-brand-500/10 px-1.5 py-px text-[10.5px] font-medium text-brand-700">{ROLE_LABEL[user.role]}</span>
      </div>
      <ul className="flex-1 overflow-y-auto px-3 pb-4 pt-2">
        {items.map((item, i) => item.section ? (
          <li key={`s-${item.section}`} className={`px-2.5 pb-1.5 text-[11px] font-medium uppercase tracking-[0.08em] text-slate-400 ${i === 0 ? "" : "pt-5"}`}>
            {item.section}
          </li>
        ) : (
          <li key={item.to} className="py-px">
            <NavLink to={item.to} end={item.end} onClick={close} className={navItemClass}>
              {({ isActive }) => (<>
                {isActive && <span className="absolute -left-3 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-gradient-to-b from-brand-400 to-violet-500 shadow-[0_0_12px_rgb(129_140_248/0.8)]" aria-hidden />}
                <item.icon size={16} className={isActive ? "text-brand-700" : "text-slate-500 transition-colors group-hover:text-slate-800"} strokeWidth={isActive ? 2.2 : 1.9} />
                {item.label}
              </>)}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="border-t border-slate-200 p-3">
        <div className="flex items-center gap-2.5 px-2 pb-2 pt-1">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-violet-500 text-snow text-xs font-semibold">{initials(user.full_name)}</span>
          <span className="min-w-0">
            <span className="block truncate text-[13px] font-medium text-slate-900">{user.full_name}</span>
            <span className="block truncate text-xs text-slate-500">{user.email}</span>
          </span>
        </div>
        <NavLink to="/profile" onClick={close} className={navItemClass}><User size={16} className="text-slate-400" /> Profile</NavLink>
        <NavLink to="/settings" onClick={close} className={navItemClass}><SlidersHorizontal size={16} className="text-slate-400" /> Account settings</NavLink>
        <button onClick={async () => { await logout(); navigate("/login"); }}
          className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-[7px] text-[13.5px] text-slate-600 transition-colors hover:bg-slate-200/50 hover:text-slate-900">
          <LogOut size={16} className="text-slate-400" /> Sign out
        </button>
      </div>
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      {/* keyboard users can jump past the sidebar links straight to the page content */}
      <a href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70] focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-slate-900 focus:shadow-pop">
        Skip to content
      </a>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-slate-200/70 bg-slate-50/70 backdrop-blur-xl lg:block">{sidebar}</aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={close} />
          <aside className="absolute inset-y-0 left-0 w-64 animate-fade-up border-r border-slate-200 bg-slate-50/95 backdrop-blur-xl">
            <button className="absolute right-3 top-3.5 rounded-md p-1.5 text-slate-500 hover:bg-slate-200/60" onClick={close} aria-label="Close menu"><X size={18} /></button>
            {sidebar}
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-60">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-slate-200/70 bg-slate-50/60 px-4 backdrop-blur-xl sm:px-6">
          <button className="-ml-1.5 rounded-md p-2 text-slate-600 hover:bg-slate-100 lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open menu"
            aria-expanded={mobileOpen}>
            <Menu size={19} />
          </button>
          <Link to={`/${user.role}`} className="lg:hidden"><Logo size={24} /></Link>
          <div className="flex-1" />
          {ai && !ai.available && (
            <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800 ring-1 ring-inset ring-amber-200">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" aria-hidden /> AI offline
            </span>
          )}
          <NotificationBell />
          <Link to="/profile" className="ml-1 flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-violet-500 text-snow text-xs font-semibold ring-offset-2 hover:ring-2 hover:ring-slate-300"
            aria-label="Your profile" title={user.full_name}>
            {initials(user.full_name)}
          </Link>
        </header>
        <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 focus:outline-none sm:px-8">
          {/* pages are lazy-loaded chunks (App.jsx); the sidebar stays visible while one downloads */}
          <Suspense fallback={<Spinner />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
