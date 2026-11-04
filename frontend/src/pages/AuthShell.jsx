/*
 * Two-column layout shared by the Login, Register, ForgotPassword and ResetPassword pages: a dark product panel
 * (headline, a live 3D interviewer and a floating preview of an interview report) and the form column.
 */

import InterviewerStage from "../components/InterviewerStage";
import Logo from "../components/Logo";

const PREVIEW = [
  { label: "Technical depth", value: 82 },
  { label: "Communication", value: 74 },
  { label: "Problem solving", value: 68 },
  { label: "Confidence", value: 57 },
];

function ReportPreview() {
  return (
    <div className="w-[300px] rounded-xl border border-snow/10 bg-night-950/80 p-4 shadow-[0_30px_60px_-20px_rgba(0,0,0,0.8)] backdrop-blur-xl" aria-hidden>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[11px] text-slate-400">Mock interview · Backend developer</p>
          <p className="mt-0.5 text-sm font-medium text-snow">Round summary</p>
        </div>
        <div className="text-right">
          <p className="num text-[28px] font-semibold leading-none tracking-tight text-snow">71</p>
          <p className="mt-1 text-[10px] text-slate-400">overall / 100</p>
        </div>
      </div>
      <div className="mt-4 space-y-2.5">
        {PREVIEW.map((r, i) => (
          <div key={r.label}>
            <div className="mb-1 flex justify-between text-[11px]">
              <span className="text-slate-600">{r.label}</span>
              <span className="num text-slate-400">{r.value}</span>
            </div>
            <div className="h-1 rounded-full bg-snow/10">
              <div className="h-1 origin-left rounded-full bg-snow/85 animate-[grow_1s_ease-out_both]" style={{ width: `${r.value}%`, animationDelay: `${300 + i * 120}ms` }} />
            </div>
          </div>
        ))}
      </div>
      <p className="mt-4 border-t border-snow/10 pt-3 text-[11px] leading-relaxed text-slate-600">
        <span className="font-medium text-snow">Next step:</span> structure answers as situation, what you did, the result.
      </p>
    </div>
  );
}

export default function AuthShell({ title, subtitle, children }) {
  return (
    <div className="flex min-h-screen">
      <div className="relative hidden w-[48%] max-w-[700px] flex-col overflow-hidden bg-night-950 text-snow lg:flex">
        {/* fine grid for depth */}
        <div className="pointer-events-none absolute inset-0 opacity-[0.07] [background-image:linear-gradient(to_right,white_1px,transparent_1px),linear-gradient(to_bottom,white_1px,transparent_1px)] [background-size:44px_44px] [mask-image:radial-gradient(ellipse_at_50%_40%,black,transparent_75%)]" aria-hidden />
        <div className="relative z-10 p-10 xl:px-14 xl:pt-12">
          <Logo inverted size={28} />
          <h2 className="mt-14 max-w-md text-[36px] font-semibold leading-[1.1] tracking-tight text-snow xl:text-[40px]">
            Practise the interview before the interview.
          </h2>
          <p className="mt-4 max-w-md text-[15px] leading-relaxed text-slate-400">
            Realistic spoken mock interviews, English practice and assessments, with feedback specific enough to act on.
          </p>
        </div>
        <div className="relative flex-1 [perspective:1400px]">
          <InterviewerStage who="aria" caption={false} className="absolute inset-y-0 left-0 right-[22%] fade-edges" />
          <div className="absolute bottom-10 right-8 z-10 animate-fade-up [transform:rotateY(-14deg)_rotateX(6deg)] [transform-style:preserve-3d] xl:right-12">
            <ReportPreview />
          </div>
        </div>
        <p className="relative z-10 px-10 pb-8 text-xs text-slate-500 xl:px-14">For students, recruiters, mentors and placement officers.</p>
      </div>
      <div className="flex flex-1 flex-col">
        <div className="flex flex-1 items-center justify-center px-5 py-12 sm:px-8">
          <div className="w-full max-w-[380px] animate-fade-up">
            <div className="mb-10 lg:hidden"><Logo size={28} /></div>
            <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
            {subtitle && <p className="mt-1.5 text-sm text-slate-500">{subtitle}</p>}
            <div className="mt-8">{children}</div>
          </div>
        </div>
        <p className="pb-6 text-center text-xs text-slate-500">
          <a href="/privacy" className="hover:underline">Privacy notice</a>
        </p>
      </div>
    </div>
  );
}
