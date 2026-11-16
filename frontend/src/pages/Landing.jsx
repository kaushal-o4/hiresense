/*
 * Public landing page (route "/" when signed out, "/home" when signed in): hero with a product preview, the six
 * features, how it works, who it is for, how the AI runs, and a final call to action. Only real, implemented
 * capabilities are described; product visuals are illustrative renderings marked as samples.
 */

import { Link } from "react-router-dom";
import {
  ArrowRight, BarChart3, BookOpenCheck, Briefcase, Check, ClipboardCheck, Cpu, FileSearch, FileText, GitCompare,
  GraduationCap, Lock, MessagesSquare, Mic, Printer, ShieldCheck, Target, UserRound, Users, Volume2,
} from "lucide-react";
import { useAuth } from "../AuthContext";
import InterviewerStage from "../components/InterviewerStage";
import Logo from "../components/Logo";
import Reveal from "../components/Reveal";
import { buttonClass } from "../components/SharedUiComponents";
import LandingNav from "./landing/LandingNav";
import ProductPreview from "./landing/ProductPreview";
import { EnglishVisual, InterviewVisual, JobsVisual, ProgressVisual, ResumeVisual } from "./landing/FeatureVisuals";

function Eyebrow({ children, className = "" }) {
  return <p className={`text-[12px] font-semibold uppercase tracking-[0.16em] text-brand-600 ${className}`}>{children}</p>;
}

function FeatureRow({ eyebrow, icon: Icon, title, text, points, visual, flip }) {
  return (
    <div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-20">
      <Reveal className={flip ? "lg:order-2" : ""}>
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><Icon size={19} /></span>
        <Eyebrow className="mt-5">{eyebrow}</Eyebrow>
        <h3 className="mt-2 text-[28px] font-bold leading-[1.15] tracking-tight text-slate-950 sm:text-[34px]">{title}</h3>
        <p className="mt-4 max-w-md text-[16px] leading-relaxed text-slate-500">{text}</p>
        <ul className="mt-6 space-y-2.5">
          {points.map((p) => (
            <li key={p} className="flex gap-2.5 text-[14.5px] text-slate-700"><Check size={17} className="mt-0.5 shrink-0 text-brand-600" />{p}</li>
          ))}
        </ul>
      </Reveal>
      <Reveal delay={120} className={`relative ${flip ? "lg:order-1" : ""}`}>
        <div className="absolute -inset-4 -z-10 rounded-2xl bg-slate-100 sm:-inset-6" aria-hidden />
        {visual}
      </Reveal>
    </div>
  );
}

const STEPS = [
  { icon: UserRound, title: "Build Your Profile", text: "Upload your resume. HireSense extracts your skills, scores the resume against your target role and lists exactly what to fix." },
  { icon: Mic, title: "Prepare With AI", text: "Take spoken mock interviews with a 3D interviewer, practise English conversation and complete assessments at your own pace." },
  { icon: Target, title: "Become Interview Ready", text: "Follow your placement-readiness score, act on question-by-question feedback and apply to roles that match your skills." },
];

const STUDENT_POINTS = [
  "Resume analysis with skill extraction and role-specific gaps",
  "Voice and text mock interviews with four interviewer styles",
  "English conversation companion with corrections and vocabulary review",
  "Assessments, rewards, streaks and a placement-readiness score",
  "Job openings and placement drives ranked by semantic match",
];
const RECRUITER_POINTS = [
  { icon: Briefcase, text: "Post jobs and receive applications from your campus" },
  { icon: FileSearch, text: "Applicants ranked by semantic skill match" },
  { icon: GitCompare, text: "Compare shortlisted candidates side by side" },
  { icon: Printer, text: "Printable candidate reports with interview evidence" },
  { icon: ClipboardCheck, text: "Create and assign assessments" },
  { icon: ShieldCheck, text: "Interview integrity reports, shared only with consent" },
];

const STACK = [
  { icon: Cpu, title: "Your choice of AI", text: "Questions, scoring and feedback run on Google Gemini or entirely on your own server with Ollama and Qwen." },
  { icon: Mic, title: "Speech recognition", text: "Answers are transcribed with Faster-Whisper, with live captions while you speak." },
  { icon: Volume2, title: "Natural voice", text: "Interviewers speak with Kokoro text-to-speech and lip-synced 3D avatars." },
  { icon: Lock, title: "Consent first", text: "If a hosted AI provider is enabled, students are asked to agree before any data leaves the server." },
];

export default function Landing() {
  const { user } = useAuth();
  const startTo = user ? `/${user.role}` : "/register";

  return (
    <div className="min-h-screen bg-white">
      <a href="#features" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-slate-900">Skip to content</a>
      <LandingNav user={user} />

      <main>
        {/* ------------------------------------------------------------ hero */}
        <section id="home" className="theme-dark relative scroll-mt-16 overflow-hidden bg-night-900">
          <div className="pointer-events-none absolute inset-0 grid-bg [mask-image:radial-gradient(ellipse_70%_60%_at_50%_0%,black,transparent)]" aria-hidden />
          <div className="pointer-events-none absolute left-1/2 top-[-18rem] h-[36rem] w-[60rem] -translate-x-1/2 rounded-full bg-[radial-gradient(closest-side,rgb(49_94_247/0.22),transparent)]" aria-hidden />
          <div className="relative mx-auto max-w-7xl px-4 pb-20 pt-16 sm:px-6 sm:pt-24 lg:px-8 lg:pb-28">
            <div className="mx-auto max-w-3xl text-center">
              <p className="mx-auto inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-1 text-[12.5px] font-medium text-slate-600 motion-safe:animate-fade-up">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-400" /> AI interview preparation and placement platform
              </p>
              <h1 className="mt-6 text-[40px] font-extrabold leading-[1.04] tracking-[-0.03em] text-slate-950 motion-safe:animate-fade-up sm:text-[56px] lg:text-[68px]">
                Your Next Opportunity Starts With Preparation.
              </h1>
              <p className="mx-auto mt-6 max-w-2xl text-[17px] leading-relaxed text-slate-500 motion-safe:animate-fade-up sm:text-[18px]">
                An intelligent career companion designed to help students prepare for interviews, improve communication,
                analyze resumes, and discover career opportunities.
              </p>
              <div className="mt-9 flex flex-col items-stretch justify-center gap-3 motion-safe:animate-fade-up sm:flex-row sm:items-center">
                <Link to={startTo} className={`${buttonClass("primary", "lg")} px-6`}>{user ? "Go to dashboard" : "Start Your Journey"} <ArrowRight size={16} /></Link>
                <a href="#features" className={`${buttonClass("secondary", "lg")} px-6`}>Explore Features</a>
              </div>
            </div>

            <Reveal delay={150} className="relative mx-auto mt-16 max-w-5xl sm:mt-20">
              <ProductPreview />
            </Reveal>
            <p className="mt-10 text-center text-[13px] text-slate-500">Your Intelligence. Your Interview. Your Future.</p>
          </div>
        </section>

        {/* ------------------------------------------------------------ features */}
        <section id="features" className="scroll-mt-16 bg-white py-24 sm:py-32">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <Reveal className="max-w-2xl">
              <Eyebrow>Features</Eyebrow>
              <h2 className="mt-3 text-[32px] font-bold leading-[1.1] tracking-tight text-slate-950 sm:text-[44px]">Everything you need between your first resume and your first offer.</h2>
              <p className="mt-4 text-[17px] leading-relaxed text-slate-500">Six connected tools, one profile. Every practice session feeds the same picture of where you stand.</p>
            </Reveal>

            <div className="mt-20 space-y-28">
              <FeatureRow eyebrow="AI Resume Analysis" icon={FileText} title="Make Your Resume Stand Out."
                text="Analyze your resume using AI and identify areas that need improvement."
                points={["Skills extracted automatically from PDF or DOCX", "Strengths, gaps and concrete fixes", "Match score for the role you are targeting"]}
                visual={<ResumeVisual />} />
              <FeatureRow flip eyebrow="AI Mock Interview" icon={Mic} title="Practice Before the Real Interview."
                text="Experience intelligent mock interviews that help you prepare for real opportunities."
                points={["Technical, HR and behavioural rounds", "Follow-up questions that adapt to your answers", "Score and feedback after every answer"]}
                visual={<InterviewVisual />} />
            </div>
          </div>
        </section>

        {/* 3D interviewer: full-bleed dark band with the real avatar */}
        <section className="theme-dark relative overflow-hidden bg-night-900" aria-labelledby="f-3d">
          <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 py-20 sm:px-6 lg:grid-cols-[1fr_1.1fr] lg:px-8 lg:py-0">
            <Reveal className="lg:py-28">
              <Eyebrow className="!text-brand-400">3D AI Interviewer</Eyebrow>
              <h2 id="f-3d" className="mt-3 text-[30px] font-bold leading-[1.1] tracking-tight text-slate-950 sm:text-[42px]">Experience a Smarter Interview.</h2>
              <p className="mt-4 max-w-md text-[16px] leading-relaxed text-slate-500">
                Interact with an AI-powered virtual interviewer using voice-based communication.
              </p>
              <dl className="mt-8 grid max-w-md grid-cols-2 gap-x-6 gap-y-5 border-t border-white/10 pt-6 text-[14px]">
                {[["Aria", "Friendly interviewer"], ["Victor", "Strict technical"], ["Marcus", "Stress interview"], ["Elena", "HR interviewer"]].map(([n, r]) => (
                  <div key={n}><dt className="font-semibold text-slate-900">{n}</dt><dd className="text-slate-500">{r}</dd></div>
                ))}
              </dl>
            </Reveal>
            <div className="relative h-[380px] sm:h-[460px] lg:h-[560px]">
              <InterviewerStage who="victor" className="absolute inset-0 fade-edges" />
            </div>
          </div>
        </section>

        {/* remaining three features: bento of different shapes */}
        <section className="bg-slate-50 py-24 sm:py-32">
          <div className="mx-auto grid max-w-7xl gap-5 px-4 sm:px-6 lg:grid-cols-6 lg:px-8">
            <Reveal className="card flex flex-col p-6 sm:p-8 lg:col-span-3 lg:row-span-2">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><MessagesSquare size={19} /></span>
              <Eyebrow className="mt-5">English Communication</Eyebrow>
              <h3 className="mt-2 text-[26px] font-bold leading-tight tracking-tight text-slate-950">Communicate With Confidence.</h3>
              <p className="mt-3 max-w-md text-[15.5px] leading-relaxed text-slate-500">Improve communication through interactive English practice and AI-powered conversations.</p>
              <div className="mt-8 flex-1"><EnglishVisual /></div>
            </Reveal>
            <Reveal delay={80} className="card p-6 sm:p-8 lg:col-span-3">
              <div className="flex items-start gap-4">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><Briefcase size={19} /></span>
                <div>
                  <Eyebrow>Intelligent Job Matching</Eyebrow>
                  <h3 className="mt-2 text-[22px] font-bold leading-tight tracking-tight text-slate-950">Find Opportunities That Match Your Skills.</h3>
                  <p className="mt-2 text-[15px] leading-relaxed text-slate-500">Discover relevant opportunities using semantic skill and job matching.</p>
                </div>
              </div>
              <div className="mt-6"><JobsVisual /></div>
            </Reveal>
            <Reveal delay={160} className="card p-6 sm:p-8 lg:col-span-3">
              <div className="flex items-start gap-4">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><BarChart3 size={19} /></span>
                <div>
                  <Eyebrow>Progress Tracking</Eyebrow>
                  <h3 className="mt-2 text-[22px] font-bold leading-tight tracking-tight text-slate-950">See Your Growth Clearly.</h3>
                  <p className="mt-2 text-[15px] leading-relaxed text-slate-500">Monitor your preparation progress and identify areas where you can improve.</p>
                </div>
              </div>
              <div className="mt-6"><ProgressVisual /></div>
            </Reveal>
          </div>
        </section>

        {/* ------------------------------------------------------------ how it works */}
        <section id="how-it-works" className="scroll-mt-16 bg-white py-24 sm:py-32">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <Reveal className="mx-auto max-w-2xl text-center">
              <Eyebrow>How It Works</Eyebrow>
              <h2 className="mt-3 text-[32px] font-bold leading-[1.1] tracking-tight text-slate-950 sm:text-[44px]">Three steps to interview ready.</h2>
            </Reveal>
            <ol className="relative mt-16 grid gap-10 md:grid-cols-3 md:gap-8">
              <div className="absolute left-[16.6%] right-[16.6%] top-6 hidden h-px bg-slate-200 md:block" aria-hidden />
              {STEPS.map((s, i) => (
                <Reveal as="li" key={s.title} delay={i * 120} className="relative text-center">
                  <span className="relative mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-900 shadow-soft">
                    <s.icon size={20} />
                    <span className="num absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-brand-500 text-[11px] font-semibold text-white">{i + 1}</span>
                  </span>
                  <h3 className="mt-6 text-[19px] font-bold text-slate-950">{s.title}</h3>
                  <p className="mx-auto mt-2 max-w-xs text-[15px] leading-relaxed text-slate-500">{s.text}</p>
                </Reveal>
              ))}
            </ol>
          </div>
        </section>

        {/* ------------------------------------------------------------ audiences */}
        <section id="students" className="scroll-mt-16 border-t border-slate-200 bg-slate-50 py-24 sm:py-32">
          <div className="mx-auto grid max-w-7xl gap-12 px-4 sm:px-6 lg:grid-cols-2 lg:gap-20 lg:px-8">
            <Reveal>
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><GraduationCap size={19} /></span>
              <Eyebrow className="mt-5">For Students</Eyebrow>
              <h2 className="mt-2 text-[30px] font-bold leading-[1.12] tracking-tight text-slate-950 sm:text-[38px]">A personal preparation workspace.</h2>
              <p className="mt-4 max-w-md text-[16px] leading-relaxed text-slate-500">Practise as often as you like, see exactly what to improve, and walk into placement season with evidence of your progress.</p>
              <Link to={startTo} className={`${buttonClass("primary", "lg")} mt-8`}>{user ? "Go to dashboard" : "Create your student account"} <ArrowRight size={16} /></Link>
            </Reveal>
            <Reveal delay={100} className="card divide-y divide-slate-100">
              {STUDENT_POINTS.map((p) => (
                <div key={p} className="flex items-start gap-3 px-5 py-4 text-[15px] text-slate-700 sm:px-6"><Check size={18} className="mt-0.5 shrink-0 text-emerald-600" /> {p}</div>
              ))}
            </Reveal>
          </div>
        </section>

        <section id="recruiters" className="scroll-mt-16 bg-white py-24 sm:py-32">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="grid gap-12 lg:grid-cols-[1fr_1.4fr] lg:gap-20">
              <Reveal>
                <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><Users size={19} /></span>
                <Eyebrow className="mt-5">For Recruiters</Eyebrow>
                <h2 className="mt-2 text-[30px] font-bold leading-[1.12] tracking-tight text-slate-950 sm:text-[38px]">Hire with evidence, not guesswork.</h2>
                <p className="mt-4 max-w-md text-[16px] leading-relaxed text-slate-500">
                  See how candidates actually perform in interviews and assessments before the first call. Recruiter accounts are approved by the placement office.
                </p>
                {!user && <Link to="/register" className={`${buttonClass("secondary", "lg")} mt-8`}>Register as a recruiter</Link>}
              </Reveal>
              <div className="grid gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 sm:grid-cols-2">
                {RECRUITER_POINTS.map(({ icon: Icon, text }, i) => (
                  <Reveal key={text} delay={i * 60} className="flex gap-3 bg-white p-6">
                    <Icon size={19} className="mt-0.5 shrink-0 text-brand-600" />
                    <p className="text-[15px] leading-snug text-slate-700">{text}</p>
                  </Reveal>
                ))}
              </div>
            </div>
            <Reveal className="mt-12 flex flex-col gap-4 rounded-xl border border-slate-200 bg-slate-50 p-6 sm:flex-row sm:items-center sm:p-8">
              <BookOpenCheck size={22} className="shrink-0 text-slate-700" />
              <p className="text-[15px] leading-relaxed text-slate-600">
                <span className="font-semibold text-slate-900">Also for mentors and placement offices.</span> Mentors follow assigned students’ progress and schedule follow-ups;
                administrators manage users, jobs, interview settings, reports and audit logs.
              </p>
            </Reveal>
          </div>
        </section>

        {/* ------------------------------------------------------------ about */}
        <section id="about" className="theme-dark scroll-mt-16 bg-night-900 py-24 sm:py-32">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <Reveal className="max-w-2xl">
              <Eyebrow className="!text-brand-400">About HireSense</Eyebrow>
              <h2 className="mt-3 text-[32px] font-bold leading-[1.1] tracking-tight text-slate-950 sm:text-[44px]">Serious AI, run responsibly.</h2>
              <p className="mt-4 text-[17px] leading-relaxed text-slate-500">
                HireSense can run on a college’s own hardware. Your institution decides which AI provider to use, and students stay in control of their data.
              </p>
            </Reveal>
            <div className="mt-14 grid gap-px overflow-hidden rounded-xl border border-white/10 bg-white/10 sm:grid-cols-2 lg:grid-cols-4">
              {STACK.map(({ icon: Icon, title, text }, i) => (
                <Reveal key={title} delay={i * 80} className="bg-night-900 p-6 sm:p-7">
                  <Icon size={20} className="text-brand-400" />
                  <h3 className="mt-5 text-[16px] font-semibold text-slate-950">{title}</h3>
                  <p className="mt-2 text-[14px] leading-relaxed text-slate-500">{text}</p>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------ final CTA */}
        <section className="bg-white py-24 sm:py-32">
          <Reveal className="mx-auto max-w-3xl px-4 text-center sm:px-6">
            <h2 className="text-[34px] font-extrabold leading-[1.08] tracking-[-0.02em] text-slate-950 sm:text-[50px]">Your Future Deserves Better Preparation.</h2>
            <p className="mx-auto mt-5 max-w-xl text-[17px] leading-relaxed text-slate-500">Prepare Smarter. Interview Better. Get Hired.</p>
            <Link to={startTo} className={`${buttonClass("primary", "lg")} mt-9 px-7`}>{user ? "Go to dashboard" : "Get Started With HireSense"} <ArrowRight size={16} /></Link>
          </Reveal>
        </section>
      </main>

      <footer className="theme-dark bg-night-900">
        <div className="mx-auto flex max-w-7xl flex-col gap-8 px-4 py-12 sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
          <div>
            <Logo size={26} inverted />
            <p className="mt-3 text-[13.5px] text-slate-500">Your Intelligence. Your Interview. Your Future.</p>
          </div>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2 text-[13.5px] text-slate-500">
            <a href="#features" className="hover:text-slate-900">Features</a>
            <a href="#how-it-works" className="hover:text-slate-900">How It Works</a>
            <Link to="/privacy" className="hover:text-slate-900">Privacy notice</Link>
            {!user && <Link to="/login" className="hover:text-slate-900">Sign In</Link>}
          </nav>
        </div>
        <div className="border-t border-white/[0.06]">
          <p className="mx-auto max-w-7xl px-4 py-5 text-[12.5px] text-slate-500 sm:px-6 lg:px-8">© {new Date().getFullYear()} HireSense</p>
        </div>
      </footer>
    </div>
  );
}
