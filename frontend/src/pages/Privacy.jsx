// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/Privacy.jsx
//
// FILE PURPOSE:
// Public privacy notice page (/privacy).
//
// WHAT THIS FILE DOES:
// 1. Loads GET /auth/privacy (through usePrivacyInfo) to know which AI provider this server uses.
// 2. Explains what data is processed and where.
// 3. Shows the AI consent card for students when needed.
//
// HOW THIS FILE WORKS:
// A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and
// modal state with useState, sends changes with post/put/patch/del and shows the result with the
// shared components from SharedUiComponents.jsx. API calls used: GET /auth/privacy.
//
// IMPORTANT FUNCTIONS:
//    Other helper functions: Privacy
//
// INPUT:
// Server privacy info.
//
// OUTPUT:
// Privacy text.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: AuthContext.jsx, components/HostedAiConsentGate.jsx
//    Used by: App.jsx
//
// IMPORTANT DEPENDENCIES:
//    react-router-dom
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* Public privacy notice (/privacy). Short and specific to how this server is configured (GET /auth/privacy). */

import { Link } from "react-router-dom";
import { usePrivacyInfo } from "../components/HostedAiConsentGate";
import { useAuth } from "../AuthContext";
import { ArrowLeft } from "lucide-react";
import Logo from "../components/Logo";

export default function Privacy() {
  const info = usePrivacyInfo();
  const { user } = useAuth();
  const hosted = info?.data_leaves_server;
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4 sm:px-6">
          <Link to="/" className="rounded-md" aria-label="HireSense home"><Logo size={26} /></Link>
          <Link to={user ? "/" : "/login"} className="inline-flex items-center gap-1.5 text-[13px] font-medium text-slate-500 hover:text-slate-900">
            <ArrowLeft size={14} /> {user ? "Back to HireSense" : "Back to sign in"}
          </Link>
        </div>
      </header>
    <main className="px-4 py-12 sm:px-6 sm:py-16">
      <article className="card mx-auto max-w-3xl space-y-8 p-6 text-[15px] leading-relaxed text-slate-600 sm:p-10">
        <header className="space-y-2 border-b border-slate-200 pb-6">
          <p className="eyebrow">Legal</p>
          <h1 className="text-[30px] font-bold tracking-tight text-slate-950">Privacy notice</h1>
          <p className="text-sm text-slate-500">How HireSense stores and processes your data on this server.</p>
        </header>

        <section className="space-y-2">
          <h2 className="text-[17px] font-semibold text-slate-950">What we store</h2>
          <p>Your account details, profile, uploaded resumes, interview questions and answers, scores and feedback,
            English practice messages, job applications and an audit log of security-relevant actions (sign-ins,
            password changes, consent). Passwords are stored only as salted hashes.</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-[17px] font-semibold text-slate-950">Who processes the AI features</h2>
          {info == null && <p>Loading…</p>}
          {info && hosted && (
            <p>This server uses <strong>Google Gemini</strong>. When you analyse a resume, take an AI interview or
              practise English, the text you provide{info.speech_to_google ? " and the audio of spoken answers" : ""} is
              sent to Google to generate questions, transcripts, scores and feedback. Google processes it under the
              Gemini API terms. We ask for your agreement before the first AI feature, record the time you agreed, and
              you can withdraw it in Settings.</p>
          )}
          {info && !hosted && (
            <p>This server runs its AI models itself. Your resume, answers and recordings are not sent to an outside AI
              service.</p>
          )}
          <p>Voice recordings are transcribed in memory and are not stored. Camera monitoring, when an interview uses
            it, analyses video in your browser; only event summaries (for example "looked away for 4 s") are sent.</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-[17px] font-semibold text-slate-950">Who can see your data</h2>
          <p>You, the placement office administrators, mentors assigned to you, and recruiters only if you choose to
            share your profile or apply to their job.</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-[17px] font-semibold text-slate-950">Your choices</h2>
          <p>You can change profile sharing and AI consent in Settings, and permanently delete your student account
            and its data there. HireSense does not sell personal data or use it for advertising.</p>
        </section>

      </article>
    </main>
    </div>
  );
}
