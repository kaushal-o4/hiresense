/*
 * Sticky top navigation of the landing page: wordmark, in-page section links, sign-in / get-started (or
 * "Go to dashboard" when signed in). On small screens the links move into a disclosure menu (Escape closes it).
 */

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Menu, X } from "lucide-react";
import Logo from "../../components/Logo";
import { buttonClass } from "../../components/SharedUiComponents";

export const SECTIONS = [
  { id: "home", label: "Home" },
  { id: "features", label: "Features" },
  { id: "how-it-works", label: "How It Works" },
  { id: "students", label: "For Students" },
  { id: "recruiters", label: "For Recruiters" },
  { id: "about", label: "About" },
];

export default function LandingNav({ user }) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const toggleRef = useRef(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === "Escape") { setOpen(false); toggleRef.current?.focus(); } };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const home = user ? `/${user.role}` : null;

  return (
    <header className={`theme-dark sticky top-0 z-40 border-b transition-colors duration-300 ${scrolled || open ? "border-white/[0.08] bg-night-900/95" : "border-transparent bg-night-900"}`}>
      <nav className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6 lg:px-8" aria-label="Main">
        <a href="#home" className="shrink-0 rounded-md" aria-label="HireSense home"><Logo size={28} inverted /></a>
        <ul className="hidden flex-1 items-center justify-center gap-1 lg:flex">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <a href={`#${s.id}`} className="rounded-md px-3 py-2 text-[13.5px] font-medium text-slate-500 transition-colors hover:text-slate-950">{s.label}</a>
            </li>
          ))}
        </ul>
        <div className="ml-auto hidden items-center gap-2 lg:ml-0 sm:flex">
          {user ? (
            <Link to={home} className={buttonClass("primary", "md")}>Go to dashboard <ArrowRight size={15} /></Link>
          ) : (
            <>
              <Link to="/login" className="rounded-md px-3 py-2 text-[13.5px] font-medium text-slate-700 transition-colors hover:text-slate-950">Sign In</Link>
              <Link to="/register" className={buttonClass("primary", "md")}>Get Started</Link>
            </>
          )}
        </div>
        <button ref={toggleRef} type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-controls="landing-menu"
          className="ml-auto flex h-10 w-10 items-center justify-center rounded-lg text-slate-700 hover:bg-white/5 sm:ml-0 lg:hidden">
          {open ? <X size={20} /> : <Menu size={20} />}<span className="sr-only">{open ? "Close menu" : "Open menu"}</span>
        </button>
      </nav>
      {open && (
        <div id="landing-menu" className="animate-fade-in border-t border-white/[0.08] px-4 pb-5 pt-2 lg:hidden">
          <ul className="space-y-0.5">
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <a href={`#${s.id}`} onClick={() => setOpen(false)} className="block rounded-lg px-3 py-3 text-[15px] font-medium text-slate-700 hover:bg-white/5 hover:text-slate-950">{s.label}</a>
              </li>
            ))}
          </ul>
          <div className="mt-3 grid gap-2 border-t border-white/[0.08] pt-4 sm:hidden">
            {user ? (
              <Link to={home} className={`${buttonClass("primary", "lg")} w-full`}>Go to dashboard</Link>
            ) : (
              <>
                <Link to="/register" className={`${buttonClass("primary", "lg")} w-full`}>Get Started</Link>
                <Link to="/login" className={`${buttonClass("secondary", "lg")} w-full`}>Sign In</Link>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
