// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/components/AppShellLayout.jsx
//
// FILE PURPOSE:
// The common frame around every signed-in page: sidebar menu, top header, notification bell and sign-
// out.
//
// MAIN RESPONSIBILITY:
// Application shell (navigation + notifications) for all four portals.
//
// WHAT THIS FILE DOES:
// 1. Shows a different sidebar menu for student, recruiter, mentor and admin (NAV table).
// 2. Adds 'Integrity review' to the menu only for mentors with the review_integrity permission.
// 3. Shows the notification bell: loads GET /notifications, marks read with POST
//    /notifications/{id}/read and /notifications/read-all.
// 4. Receives live notification signals through live/notificationStream.js.
// 5. Top bar: page search (Ctrl+K command palette over the menu), help, theme switcher, notifications and a
//    profile menu (profile, account settings, sign out); renders the current page in <Outlet/>.
//
// HOW THIS FILE WORKS:
// Layout reads the user from useAuth(), builds the menu from NAV[user.role] and wraps the routed page
// in a Suspense block (pages are lazy-loaded). NotificationBell subscribes to the live stream and
// reloads the list when a signal arrives.
//
// IMPORTANT FUNCTIONS:
//    - Layout()
//        The page frame: sidebar (desktop + mobile drawer), header and page outlet.
//    - NotificationBell()
//        Bell icon with unread count and a dropdown of the latest notifications.
//    Other helper functions: initials, navItemClass
//
// IMPORTANT VARIABLES / STATE:
//    - NAV
//        Menu items for each role (link, label, icon, section headings).
//
// INPUT:
// Logged-in user (role, permissions), notification API responses, live stream signals.
//
// OUTPUT:
// Rendered navigation and the current page.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: AuthContext.jsx, apiClient.js, components/Logo.jsx, components/SharedUiComponents.jsx,
//    live/notificationStream.js
//    Used by: App.jsx
//
// EXECUTION FLOW:
//    User logs in
//       |
//       v
//    Layout builds the menu for the user's role
//       |
//       v
//    Bell loads notifications and listens for live signals
//       |
//       v
//    Clicking a menu item changes the routed page
//
// IMPORTANT DEPENDENCIES:
//    lucide-react, react, react-router-dom
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* Shared application shell: sidebar, top bar (search, help, theme, notifications, profile menu) and page outlet. */

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Award, BarChart3, Bell, BookOpen, Briefcase, CalendarClock, ChevronDown, ClipboardCheck, ClipboardList, CornerDownLeft,
  FileText, Gauge, GraduationCap, HelpCircle, Keyboard, LayoutDashboard, LogOut, Menu, MessagesSquare, Mic, Monitor,
  Moon, ScrollText, Search, Settings, ShieldAlert, ShieldCheck, SlidersHorizontal, Sun, Target, User, Users, X,
} from "lucide-react";
import { useAuth } from "../AuthContext";
import { get, post } from "../apiClient";
import { subscribeNotifications } from "../live/notificationStream";
import Logo from "./Logo";
import { fmtDateTime, PageSkeleton } from "./SharedUiComponents";
import { useTheme } from "./ThemeContext";

// `section` starts a new labelled group in the sidebar. Every item is a real route (App.jsx).
const NAV = {
  student: [
    { to: "/student", label: "Overview", icon: LayoutDashboard, end: true },
    { section: "Preparation" },
    { to: "/student/resume", label: "Resume analysis", icon: FileText },
    { to: "/student/interviews", label: "Mock interviews", icon: Mic },
    { to: "/student/english", label: "Communication practice", icon: MessagesSquare },
    { to: "/student/assessments", label: "Assessments", icon: ClipboardCheck },
    { section: "Career" },
    { to: "/student/jobs", label: "Job opportunities", icon: Briefcase }, // job openings + placement drives
    { to: "/student/applications", label: "My applications", icon: ClipboardList },
    { to: "/student/mentoring", label: "Mentoring", icon: Target },
    { section: "Growth" },
    { to: "/student/progress", label: "My progress", icon: BarChart3 }, // overview, full report, practice history
    { to: "/student/rewards", label: "Rewards & challenges", icon: Award },
  ],
  recruiter: [
    { to: "/recruiter", label: "Overview", icon: LayoutDashboard, end: true },
    { section: "Hiring" },
    { to: "/recruiter/jobs", label: "Job listings", icon: Briefcase },
    { to: "/recruiter/candidates", label: "Candidates", icon: Users },
    { to: "/recruiter/assessments", label: "Assessments", icon: ClipboardCheck },
    { section: "Reports" },
    { to: "/recruiter/security", label: "Interview integrity", icon: ShieldAlert },
  ],
  mentor: [
    { to: "/mentor", label: "Overview", icon: LayoutDashboard, end: true },
    { section: "Mentoring" },
    { to: "/mentor/students", label: "Students", icon: GraduationCap },
    { to: "/mentor/sessions", label: "Sessions & feedback", icon: CalendarClock },
  ],
  admin: [
    { to: "/admin", label: "Overview", icon: LayoutDashboard, end: true },
    { section: "People" },
    { to: "/admin/users", label: "User management", icon: Users },
    { to: "/admin/assignments", label: "Mentor assignments", icon: GraduationCap },
    { section: "Programme" },
    { to: "/admin/jobs", label: "Jobs & placements", icon: Briefcase },
    { to: "/admin/interview-config", label: "Interview setup", icon: BookOpen },
    { to: "/admin/assessments", label: "Assessments", icon: ClipboardCheck },
    { to: "/admin/rewards", label: "Rewards & badges", icon: Award },
    { section: "System" },
    { to: "/admin/reports", label: "Reports", icon: Gauge },
    { to: "/admin/monitoring", label: "AI & monitoring", icon: ShieldAlert },
    { to: "/admin/audit", label: "Audit logs", icon: ScrollText },
    { to: "/admin/settings", label: "System settings", icon: Settings },
  ],
};
// Pages every role has; shown in search and the profile menu (not the sidebar).
const COMMON = [
  { to: "/profile", label: "Profile", icon: User },
  { to: "/settings", label: "Account settings", icon: SlidersHorizontal },
  { to: "/notifications", label: "Notifications", icon: Bell },
  { to: "/privacy", label: "Privacy notice", icon: ShieldCheck },
];

const ROLE_LABEL = { student: "Student", recruiter: "Recruiter", mentor: "Mentor", admin: "Admin" };

const initials = (name = "") => name.split(" ").filter(Boolean).map((p) => p[0]).slice(0, 2).join("").toUpperCase();

/** Closes a popover on outside click or Escape. */
function useDismiss(open, setOpen, ref) {
  useEffect(() => {
    if (!open) return undefined;
    const onClick = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onClick); document.removeEventListener("keydown", onKey); };
  }, [open, setOpen, ref]);
}

const ICON_BTN = "relative flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900";
const POPOVER = "absolute right-0 z-40 mt-2 origin-top-right animate-scale-in overflow-hidden rounded-xl border border-slate-200 bg-white shadow-pop";

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState({ items: [], unread: 0 });
  const ref = useRef(null);
  const navigate = useNavigate();
  useDismiss(open, setOpen, ref);

  const load = async () => {
    try {
      setData(await get("/notifications", { page_size: 8 }));
    } catch { /* ignore refresh errors; the next signal or poll retries */ }
  };

  useEffect(() => {
    load();
    // Live updates over Server-Sent Events, with backoff reconnects and a polling fallback (live/notificationStream.js).
    let timer = null;
    const unsubscribe = subscribeNotifications(() => {
      clearTimeout(timer);
      timer = setTimeout(load, 150); // coalesce bursts (several notifications in one action)
    });
    return () => { unsubscribe(); clearTimeout(timer); };
  }, []);

  const openItem = async (n) => {
    if (!n.read) await post(`/notifications/${n.id}/read`).catch(() => {});
    setOpen(false);
    load();
    if (n.link) navigate(n.link);
  };

  return (
    <div className="relative" ref={ref}>
      <button className={`${ICON_BTN} ${open ? "bg-slate-100 text-slate-900" : ""}`}
        onClick={() => { setOpen(!open); load(); }}
        aria-label={`Notifications (${data.unread} unread)`} aria-expanded={open} aria-haspopup="true">
        <Bell size={18} strokeWidth={1.9} />
        {data.unread > 0 && (
          <span className="num absolute right-1 top-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-brand-500 px-1 text-[10px] font-semibold text-snow ring-2 ring-white">
            {data.unread > 99 ? "99+" : data.unread}
          </span>
        )}
      </button>
      {open && (
        <div className={`${POPOVER} w-[22rem] max-w-[calc(100vw-2rem)]`}>
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <span className="text-sm font-semibold text-slate-900">Notifications</span>
            {data.unread > 0 && (
              <button className="text-xs font-medium text-brand-600 hover:text-brand-700" onClick={async () => { await post("/notifications/read-all"); load(); }}>
                Mark all as read
              </button>
            )}
          </div>
          <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
            {data.items.length === 0 && (
              <li className="flex flex-col items-center gap-2 px-4 py-10 text-center">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-400"><Bell size={16} /></span>
                <span className="text-sm text-slate-500">You're all caught up.</span>
              </li>
            )}
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
          <Link to="/notifications" onClick={() => setOpen(false)} className="block border-t border-slate-200 py-2.5 text-center text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900">
            View all notifications
          </Link>
        </div>
      )}
    </div>
  );
}

const THEMES = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

function ThemeMenu() {
  const { theme, resolved, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useDismiss(open, setOpen, ref);
  const Icon = resolved === "dark" ? Moon : Sun;
  return (
    <div className="relative" ref={ref}>
      <button className={`${ICON_BTN} ${open ? "bg-slate-100 text-slate-900" : ""}`} onClick={() => setOpen(!open)}
        aria-label="Change colour theme" aria-expanded={open} aria-haspopup="true">
        <Icon size={18} strokeWidth={1.9} />
      </button>
      {open && (
        <div className={`${POPOVER} w-40 p-1`} role="menu">
          {THEMES.map((t) => (
            <button key={t.value} role="menuitemradio" aria-checked={theme === t.value} onClick={() => { setTheme(t.value); setOpen(false); }}
              className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors ${theme === t.value ? "bg-slate-100 font-medium text-slate-950" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}>
              <t.icon size={15} /> {t.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function HelpMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useDismiss(open, setOpen, ref);
  return (
    <div className="relative hidden sm:block" ref={ref}>
      <button className={`${ICON_BTN} ${open ? "bg-slate-100 text-slate-900" : ""}`} onClick={() => setOpen(!open)}
        aria-label="Help" aria-expanded={open} aria-haspopup="true">
        <HelpCircle size={18} strokeWidth={1.9} />
      </button>
      {open && (
        <div className={`${POPOVER} w-72 p-4 text-sm`}>
          <p className="font-semibold text-slate-900">Help</p>
          <p className="mt-1 text-slate-500">Use the menu on the left to move between sections. Your data is only shown to people your placement office allows.</p>
          <p className="mt-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500"><Keyboard size={13} /> Shortcuts</p>
          <ul className="mt-2 space-y-1.5 text-slate-600">
            <li className="flex items-center justify-between">Search pages <span className="flex gap-1"><kbd className="kbd">Ctrl</kbd><kbd className="kbd">K</kbd></span></li>
            <li className="flex items-center justify-between">Close a dialog <kbd className="kbd">Esc</kbd></li>
          </ul>
          <div className="mt-4 border-t border-slate-200 pt-3">
            <Link to="/privacy" onClick={() => setOpen(false)} className="link text-sm">Privacy notice</Link>
          </div>
        </div>
      )}
    </div>
  );
}

function ProfileMenu({ user, onSignOut }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useDismiss(open, setOpen, ref);
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="true" aria-label="Your account menu"
        className={`ml-1 flex items-center gap-2 rounded-lg py-1 pl-1 pr-1.5 transition-colors hover:bg-slate-100 ${open ? "bg-slate-100" : ""}`}>
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-950 text-[11px] font-semibold text-white">{initials(user.full_name)}</span>
        <span className="hidden max-w-[9rem] truncate text-[13px] font-medium text-slate-800 md:block">{user.full_name}</span>
        <ChevronDown size={14} className={`hidden text-slate-400 transition-transform md:block ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className={`${POPOVER} w-64`}>
          <div className="border-b border-slate-200 px-4 py-3">
            <p className="truncate text-sm font-semibold text-slate-900">{user.full_name}</p>
            <p className="truncate text-xs text-slate-500">{user.email}</p>
            <span className="mt-2 inline-flex rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">{ROLE_LABEL[user.role]} account</span>
          </div>
          <div className="p-1">
            <Link to="/profile" onClick={() => setOpen(false)} className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-slate-700 hover:bg-slate-50 hover:text-slate-950"><User size={15} className="text-slate-400" /> Profile</Link>
            <Link to="/settings" onClick={() => setOpen(false)} className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-slate-700 hover:bg-slate-50 hover:text-slate-950"><SlidersHorizontal size={15} className="text-slate-400" /> Account settings</Link>
          </div>
          <div className="border-t border-slate-200 p-1">
            <button onClick={onSignOut} className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-slate-700 hover:bg-slate-50 hover:text-slate-950">
              <LogOut size={15} className="text-slate-400" /> Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Ctrl/Cmd+K page search over the user's own menu (navigation only - it does not search records). */
function CommandPalette({ open, onClose, items }) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const results = useMemo(() => {
    const t = q.trim().toLowerCase();
    return items.filter((i) => !t || i.label.toLowerCase().includes(t) || (i.group || "").toLowerCase().includes(t));
  }, [q, items]);
  useEffect(() => { if (open) { setQ(""); setActive(0); setTimeout(() => inputRef.current?.focus(), 0); } }, [open]);
  useEffect(() => setActive(0), [q]);
  if (!open) return null;
  const go = (i) => { onClose(); navigate(i.to); };
  const onKey = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(results.length - 1, a + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
    else if (e.key === "Enter" && results[active]) { e.preventDefault(); go(results[active]); }
    else if (e.key === "Escape") onClose();
  };
  return (
    <div className="fixed inset-0 z-[60] flex animate-fade-in items-start justify-center bg-night-900/40 p-4 pt-[12vh] backdrop-blur-[2px]" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Search pages" className="w-full max-w-lg animate-scale-in overflow-hidden rounded-xl border border-slate-200 bg-white shadow-pop" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-slate-200 px-4">
          <Search size={17} className="shrink-0 text-slate-400" />
          <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} placeholder="Search pages…"
            aria-label="Search pages" role="combobox" aria-expanded="true" aria-controls="hs-palette-list"
            aria-activedescendant={results[active] ? `hs-pal-${active}` : undefined}
            className="h-12 w-full border-0 bg-transparent text-[15px] text-slate-900 placeholder:text-slate-400 focus:outline-none" />
          <kbd className="kbd">Esc</kbd>
        </div>
        <ul id="hs-palette-list" role="listbox" className="max-h-80 overflow-y-auto p-1.5">
          {results.length === 0 && <li className="px-3 py-8 text-center text-sm text-slate-500">No pages match "{q}".</li>}
          {results.map((i, idx) => (
            <li key={i.to} id={`hs-pal-${idx}`} role="option" aria-selected={idx === active}>
              <button onMouseEnter={() => setActive(idx)} onClick={() => go(i)}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm ${idx === active ? "bg-slate-100 text-slate-950" : "text-slate-700"}`}>
                <i.icon size={16} className="shrink-0 text-slate-400" />
                <span className="flex-1 truncate">{i.label}</span>
                {i.group && <span className="text-xs text-slate-400">{i.group}</span>}
                {idx === active && <CornerDownLeft size={13} className="text-slate-400" />}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

const navItemClass = ({ isActive }) => `group relative flex items-center gap-2.5 rounded-lg px-2.5 py-[7px] text-[13.5px] transition-colors ${
  isActive ? "bg-white font-medium text-slate-950 shadow-soft ring-1 ring-slate-200" : "text-slate-600 hover:bg-slate-200/50 hover:text-slate-900"}`;

export default function Layout() {
  const { user, ai, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // Escape closes the mobile menu, like clicking the dark backdrop does.
  useEffect(() => {
    if (!mobileOpen) return undefined;
    const onKey = (e) => e.key === "Escape" && setMobileOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mobileOpen]);
  // Ctrl/Cmd+K opens page search.
  useEffect(() => {
    const onKey = (e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setSearchOpen((o) => !o); } };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);
  // close the drawer after navigating
  useEffect(() => setMobileOpen(false), [location.pathname]);

  const items = [...(NAV[user.role] || []),
    // only mentors explicitly authorised by an admin review interview monitoring
    ...(user.role === "mentor" && (user.permissions || []).includes("review_integrity")
      ? [{ section: "Review" }, { to: "/mentor/integrity", label: "Integrity review", icon: ShieldAlert }] : [])];
  const searchItems = useMemo(() => {
    let group = ROLE_LABEL[user.role];
    const out = [];
    for (const i of items) { if (i.section) group = i.section; else out.push({ ...i, group }); }
    return [...out, ...COMMON.map((c) => ({ ...c, group: "Account" }))];
  }, [user.role, items.length]); // eslint-disable-line react-hooks/exhaustive-deps
  const signOut = async () => { await logout(); navigate("/login"); };
  const close = () => setMobileOpen(false);

  const sidebar = (
    <nav className="flex h-full flex-col" aria-label="Main">
      <div className="flex h-16 items-center justify-between gap-2 px-5">
        <Link to={`/${user.role}`} onClick={close} className="rounded-md focus-visible:outline-offset-4"><Logo size={26} /></Link>
      </div>
      <div className="px-5 pb-2">
        <span className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-600">
          <span className="h-1.5 w-1.5 rounded-full bg-brand-500" aria-hidden /> {ROLE_LABEL[user.role]} portal
        </span>
      </div>
      <ul className="flex-1 overflow-y-auto px-3 pb-4 pt-1">
        {items.map((item, i) => item.section ? (
          <li key={`s-${item.section}`} className={`px-2.5 pb-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-400 ${i === 0 ? "" : "pt-5"}`}>
            {item.section}
          </li>
        ) : (
          <li key={item.to} className="py-px">
            <NavLink to={item.to} end={item.end} onClick={close} className={navItemClass}>
              {({ isActive }) => (<>
                <item.icon size={16} className={isActive ? "text-brand-600" : "text-slate-400 transition-colors group-hover:text-slate-700"} strokeWidth={isActive ? 2.2 : 1.9} />
                {item.label}
              </>)}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="border-t border-slate-200 p-3">
        <NavLink to="/settings" onClick={close} className={navItemClass}><Settings size={16} className="text-slate-400" /> Account settings</NavLink>
        <div className="mt-2 flex items-center gap-2.5 rounded-lg px-2.5 py-2">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-950 text-xs font-semibold text-white">{initials(user.full_name)}</span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-medium text-slate-900">{user.full_name}</span>
            <span className="block truncate text-xs text-slate-500">{user.email}</span>
          </span>
          <button onClick={signOut} className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-200/60 hover:text-slate-800" aria-label="Sign out" title="Sign out">
            <LogOut size={15} />
          </button>
        </div>
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
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-slate-200 bg-slate-50 print:!hidden lg:block">{sidebar}</aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 animate-fade-in bg-night-900/50" onClick={close} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw] animate-slide-in border-r border-slate-200 bg-slate-50 shadow-pop">
            <button className="absolute right-3 top-4 rounded-md p-1.5 text-slate-500 hover:bg-slate-200/60" onClick={close} aria-label="Close menu"><X size={18} /></button>
            {sidebar}
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-64 print:!pl-0">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-2 border-b border-slate-200 bg-white/85 px-4 backdrop-blur-md print:!hidden sm:px-6">
          <button className="-ml-1.5 rounded-md p-2 text-slate-600 hover:bg-slate-100 lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open menu"
            aria-expanded={mobileOpen}>
            <Menu size={19} />
          </button>
          <Link to={`/${user.role}`} className="sm:hidden" aria-label="HireSense home"><Logo size={24} wordmark={false} /></Link>
          <button onClick={() => setSearchOpen(true)} aria-label="Search pages (Ctrl+K)"
            className="hidden h-9 w-full max-w-xs items-center gap-2.5 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-400 transition-colors hover:border-slate-300 hover:text-slate-500 sm:flex">
            <Search size={15} /> <span className="flex-1 text-left">Search pages…</span>
            <span className="flex gap-0.5"><kbd className="kbd">Ctrl</kbd><kbd className="kbd">K</kbd></span>
          </button>
          <div className="flex-1" />
          {ai && !ai.available && (
            <span className="hidden items-center gap-1.5 whitespace-nowrap rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-200 sm:inline-flex"
              title="AI features are temporarily unavailable">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" aria-hidden /> AI offline
            </span>
          )}
          <button onClick={() => setSearchOpen(true)} className={`${ICON_BTN} sm:hidden`} aria-label="Search pages"><Search size={18} /></button>
          <HelpMenu />
          <ThemeMenu />
          <NotificationBell />
          <ProfileMenu user={user} onSignOut={signOut} />
        </header>
        <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 focus:outline-none sm:px-8 lg:py-10">
          {/* pages are lazy-loaded chunks (App.jsx); the shell stays visible while one downloads */}
          <Suspense fallback={<PageSkeleton />}>
            <div key={location.pathname} className="animate-fade-up">
              <Outlet />
            </div>
          </Suspense>
        </main>
      </div>
      <CommandPalette open={searchOpen} onClose={() => setSearchOpen(false)} items={searchItems} />
    </div>
  );
}
