/* Public privacy notice (/privacy). Short and specific to how this server is configured (GET /auth/privacy). */

import { Link } from "react-router-dom";
import { usePrivacyInfo } from "../components/AIConsent";
import { useAuth } from "../auth";

export default function Privacy() {
  const info = usePrivacyInfo();
  const { user } = useAuth();
  const hosted = info?.data_leaves_server;
  return (
    <main className="min-h-screen bg-slate-50 px-4 py-12">
      <article className="mx-auto max-w-2xl space-y-6 text-sm leading-relaxed text-slate-600">
        <header className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">HireSense</p>
          <h1 className="text-2xl font-semibold text-slate-900">Privacy notice</h1>
        </header>

        <section className="space-y-2">
          <h2 className="text-base font-semibold text-slate-900">What we store</h2>
          <p>Your account details, profile, uploaded resumes, interview questions and answers, scores and feedback,
            English practice messages, job applications and an audit log of security-relevant actions (sign-ins,
            password changes, consent). Passwords are stored only as salted hashes.</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold text-slate-900">Who processes the AI features</h2>
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
          <h2 className="text-base font-semibold text-slate-900">Who can see your data</h2>
          <p>You, the placement office administrators, mentors assigned to you, and recruiters only if you choose to
            share your profile or apply to their job.</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold text-slate-900">Your choices</h2>
          <p>You can change profile sharing and AI consent in Settings, and permanently delete your student account
            and its data there. HireSense does not sell personal data or use it for advertising.</p>
        </section>

        <p>
          <Link to={user ? "/" : "/login"} className="text-brand-600 hover:underline">
            {user ? "Back to HireSense" : "Back to sign in"}
          </Link>
        </p>
      </article>
    </main>
  );
}
